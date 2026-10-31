"""
Anthropic Messages API provider implementation.
Supports prompt caching (ephemeral cache control) and extended thinking blocks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Messages API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("anthropic", config.api_key)
        if not self.api_key:
            raise ProviderError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if self.config.enable_caching:
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        headers.update(self.config.extra_headers)

        # Build payload
        max_tokens = self.config.max_tokens or 2048
        if self.config.enable_thinking and self.config.thinking_budget:
            if max_tokens <= self.config.thinking_budget:
                max_tokens = self.config.thinking_budget + 1024

        formatted_messages: List[Dict[str, Any]] = []
        for i, msg in enumerate(messages):
            if msg.role not in ("user", "assistant"):
                continue

            content_blocks: List[Dict[str, Any]] = []

            # If previous assistant turn had thinking, Anthropic requires thinking block preceded in history if thinking enabled
            if msg.role == "assistant" and msg.thinking:
                content_blocks.append({
                    "type": "thinking",
                    "thinking": msg.thinking,
                    "signature": msg.metadata.get("thinking_signature", ""),
                })

            content_blocks.append({
                "type": "text",
                "text": msg.content,
            })

            # Apply cache_control to earlier turns if caching enabled
            if self.config.enable_caching and i > 0 and i == len(messages) - 2:
                content_blocks[-1]["cache_control"] = {"type": "ephemeral"}

            formatted_messages.append({
                "role": msg.role,
                "content": content_blocks,
            })

        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
        }

        # System prompt with caching if enabled
        if system_prompt:
            if self.config.enable_caching:
                body["system"] = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                body["system"] = system_prompt

        # Thinking configuration
        if self.config.enable_thinking and self.config.thinking_budget:
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget,
            }
            # Anthropic requires temperature=1 when thinking is enabled
            body["temperature"] = 1.0
        elif self.config.temperature is not None:
            body["temperature"] = self.config.temperature

        body.update(self.config.extra_body)

        response = self._execute_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body=body,
        )

        res_json = response.json()

        # Parse response blocks
        text_parts: List[str] = []
        thinking_parts: List[str] = []
        thinking_signature: Optional[str] = None

        for block in res_json.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinking_parts.append(block.get("thinking", ""))
                thinking_signature = block.get("signature")

        content = "".join(text_parts).strip()
        thinking = "\n\n".join(thinking_parts).strip() if thinking_parts else None

        # Usage
        usage_data = res_json.get("usage", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)
        cache_read = usage_data.get("cache_read_input_tokens", 0)
        cache_creation = usage_data.get("cache_creation_input_tokens", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cached_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )

        metadata = {
            "stop_reason": res_json.get("stop_reason"),
            "model": res_json.get("model"),
            "request_id": response.headers.get("request-id"),
        }
        if thinking_signature:
            metadata["thinking_signature"] = thinking_signature

        return ProviderResponse(
            content=content,
            thinking=thinking,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

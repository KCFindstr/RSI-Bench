"""
Google Gemini Interactions API provider implementation (/v1beta/interactions).
Supports unified agent/model interaction, server-side multi-turn state via
previous_interaction_id, thought/reasoning extraction from steps/outputs,
and context caching token tracking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class GeminiInteractionsProvider(BaseProvider):
    """Provider for Google Gemini Interactions API (/v1beta/interactions)."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = (
            get_api_key_for_provider("gemini_interactions", config.api_key)
            or get_api_key_for_provider("gemini", config.api_key)
        )
        if not self.api_key:
            raise ProviderError(
                "Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
            )
        self.base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self._last_interaction_id: Optional[str] = None

    def reset_conversation(self) -> None:
        """Reset conversation state tracking."""
        self._last_interaction_id = None

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/interactions"

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        # In multi-turn Interactions API, input is the latest user turn
        # while context is preserved server-side via previous_interaction_id
        latest_message = messages[-1] if messages else Message(role="user", content=self.config.prompt)
        current_input = latest_message.content

        body: Dict[str, Any] = {
            "model": self.config.model,
            "input": current_input,
            "store": True,  # Required for server-side state retention
        }

        # If we have a previous interaction id in this conversation, link it
        if self._last_interaction_id and len(messages) > 1:
            body["previous_interaction_id"] = self._last_interaction_id

        if system_prompt:
            body["system_instruction"] = {
                "parts": [{"text": system_prompt}]
            }

        generation_config: Dict[str, Any] = {}
        if self.config.temperature is not None:
            generation_config["temperature"] = self.config.temperature
        if self.config.max_tokens:
            generation_config["max_output_tokens"] = self.config.max_tokens

        # Thinking configuration for Gemini 2.0 / 2.5
        if self.config.enable_thinking:
            budget = self.config.thinking_budget if self.config.thinking_budget is not None else 1024
            generation_config["thinking_config"] = {
                "thinking_budget": budget
            }

        if generation_config:
            body["generation_config"] = generation_config

        body.update(self.config.extra_body)

        response = self._execute_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body=body,
            params={"key": self.api_key},
        )

        res_json = response.json()

        # Update last interaction id for conversation continuity
        interaction_id = res_json.get("id")
        if interaction_id:
            self._last_interaction_id = interaction_id

        # Extract content and reasoning/thinking traces
        content_parts: List[str] = []
        thinking_parts: List[str] = []

        # 1. Parse 'steps' array (modern Interactions schema)
        steps = res_json.get("steps", [])
        for step in steps:
            step_type = step.get("type", "")
            if step_type in ("thought", "thinking"):
                text = step.get("text") or step.get("summary") or ""
                if text:
                    thinking_parts.append(text)
            elif step_type in ("model_output", "text", "message"):
                text = step.get("text") or ""
                if not text and "parts" in step:
                    text = "".join(p.get("text", "") for p in step["parts"] if isinstance(p, dict))
                if text:
                    content_parts.append(text)

        # 2. Parse 'outputs' array (standard Interactions schema)
        outputs = res_json.get("outputs", [])
        for out in outputs:
            out_type = out.get("type", "")
            if out_type in ("thought", "thinking"):
                text = out.get("text") or out.get("summary") or ""
                if text:
                    thinking_parts.append(text)
            elif out_type in ("text", "model_output"):
                text = out.get("text", "")
                if text:
                    content_parts.append(text)

        # 3. Fallbacks for top-level output fields
        if not content_parts:
            if "output_text" in res_json:
                content_parts.append(res_json["output_text"])
            elif "text" in res_json:
                content_parts.append(res_json["text"])
            elif "candidates" in res_json:
                cand = res_json["candidates"][0]
                for part in cand.get("content", {}).get("parts", []):
                    if part.get("thought") is True:
                        thinking_parts.append(part.get("text", ""))
                    else:
                        content_parts.append(part.get("text", ""))

        content = "".join(content_parts).strip()
        thinking = "\n\n".join(thinking_parts).strip() if thinking_parts else None

        # Token Usage & Context Caching
        usage_data = res_json.get("usage", {}) or res_json.get("usageMetadata", {})
        prompt_tokens = usage_data.get("total_input_tokens") or usage_data.get("promptTokenCount", 0)
        completion_tokens = usage_data.get("total_output_tokens") or usage_data.get("candidatesTokenCount", 0)
        total_tokens = usage_data.get("total_tokens") or usage_data.get(
            "totalTokenCount", prompt_tokens + completion_tokens
        )
        reasoning_tokens = usage_data.get("total_thought_tokens") or usage_data.get("thoughtTokenCount", 0)
        cached_tokens = usage_data.get("cached_tokens") or usage_data.get("cachedContentTokenCount", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        metadata = {
            "interaction_id": interaction_id,
            "previous_interaction_id": body.get("previous_interaction_id"),
            "model": res_json.get("model", self.config.model),
            "status": res_json.get("status"),
        }

        return ProviderResponse(
            content=content,
            thinking=thinking,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

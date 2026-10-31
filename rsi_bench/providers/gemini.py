"""
Google Gemini provider implementation (supporting Interactions and generateContent APIs).
Supports thinking trace extraction from thought parts and context caching token counts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("gemini", config.api_key)
        if not self.api_key:
            raise ProviderError("Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        model = self.config.model
        url = f"{self.base_url}/models/{model}:generateContent"

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        # Convert messages to Gemini contents format
        # Gemini uses "user" and "model" roles
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            role = "model" if msg.role == "assistant" else "user"
            parts: List[Dict[str, Any]] = []
            if msg.thinking and role == "model":
                parts.append({"text": msg.thinking, "thought": True})
            parts.append({"text": msg.content})
            contents.append({
                "role": role,
                "parts": parts,
            })

        body: Dict[str, Any] = {
            "contents": contents,
        }

        if system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        generation_config: Dict[str, Any] = {}
        if self.config.temperature is not None:
            generation_config["temperature"] = self.config.temperature
        if self.config.max_tokens:
            generation_config["maxOutputTokens"] = self.config.max_tokens

        # Thinking configuration for Gemini 2.0 / 2.5
        if self.config.enable_thinking:
            budget = self.config.thinking_budget if self.config.thinking_budget is not None else 1024
            generation_config["thinkingConfig"] = {
                "thinkingBudget": budget
            }

        if generation_config:
            body["generationConfig"] = generation_config

        body.update(self.config.extra_body)

        response = self._execute_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body=body,
            params={"key": self.api_key},
        )

        res_json = response.json()
        candidates = res_json.get("candidates", [])
        if not candidates:
            # Check for error or prompt feedback block
            feedback = res_json.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                raise ProviderError(f"Gemini blocked prompt: {block_reason}")
            raise ProviderError(f"No candidates returned from Gemini API: {res_json}")

        candidate = candidates[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])

        content_texts: List[str] = []
        thinking_texts: List[str] = []

        for part in parts:
            part_text = part.get("text", "")
            # Check if this part is thinking/thought
            if part.get("thought") is True or "thought" in part:
                thinking_texts.append(part_text)
            else:
                content_texts.append(part_text)

        content = "".join(content_texts).strip()
        thinking = "\n\n".join(thinking_texts).strip() if thinking_texts else None

        # Usage
        usage_data = res_json.get("usageMetadata", {})
        prompt_tokens = usage_data.get("promptTokenCount", 0)
        completion_tokens = usage_data.get("candidatesTokenCount", 0)
        total_tokens = usage_data.get("totalTokenCount", prompt_tokens + completion_tokens)
        cached_tokens = usage_data.get("cachedContentTokenCount", 0)
        reasoning_tokens = usage_data.get("thoughtTokenCount", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        metadata = {
            "finishReason": candidate.get("finishReason"),
            "model": model,
        }

        return ProviderResponse(
            content=content,
            thinking=thinking,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

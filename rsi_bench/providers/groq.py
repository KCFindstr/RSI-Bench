"""
Groq API provider implementation (/openai/v1/chat/completions).
High-speed inference provider supporting reasoning models like DeepSeek-R1-distill.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class GroqProvider(BaseProvider):
    """Provider for Groq API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("groq", config.api_key)
        if not self.api_key:
            raise ProviderError("Groq API key is required. Set GROQ_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.groq.com/openai/v1").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted_messages.append({"role": msg.role, "content": msg.content})

        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
        }

        if self.config.temperature is not None:
            body["temperature"] = self.config.temperature

        if self.config.max_tokens:
            body["max_tokens"] = self.config.max_tokens

        body.update(self.config.extra_body)

        response = self._execute_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body=body,
        )

        res_json = response.json()
        choices = res_json.get("choices", [])
        if not choices:
            raise ProviderError(f"No choices returned from Groq API: {res_json}")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        reasoning = message.get("reasoning") or message.get("reasoning_content")

        usage_data = res_json.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        prompt_details = usage_data.get("prompt_tokens_details", {})
        cached_tokens = prompt_details.get("cached_tokens", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
        )

        metadata = {
            "finish_reason": choice.get("finish_reason"),
            "model": res_json.get("model"),
            "queue_time": usage_data.get("queue_time"),
            "total_time": usage_data.get("total_time"),
        }

        return ProviderResponse(
            content=content,
            thinking=reasoning,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

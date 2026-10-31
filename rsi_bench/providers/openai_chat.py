"""
OpenAI standard Chat Completions provider implementation (/v1/chat/completions).
Supports reasoning models (o1, o3-mini) with reasoning_effort, cached prompt tokens,
and reasoning token tracking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class OpenAIChatProvider(BaseProvider):
    """Provider for OpenAI Chat Completions API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("openai_chat", config.api_key)
        if not self.api_key:
            raise ProviderError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

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
            # For reasoning models like o1, developer/system message can be role "developer" or "system"
            formatted_messages.append({"role": "developer" if self._is_reasoning_model() else "system", "content": system_prompt})

        for msg in messages:
            msg_dict: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            formatted_messages.append(msg_dict)

        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
        }

        # Handle temperature and tokens depending on reasoning vs non-reasoning models
        if self._is_reasoning_model():
            if self.config.enable_thinking:
                body["reasoning_effort"] = "medium"
            if self.config.max_tokens:
                body["max_completion_tokens"] = self.config.max_tokens
        else:
            if self.config.temperature is not None:
                body["temperature"] = self.config.temperature
            if self.config.max_tokens:
                body["max_tokens"] = self.config.max_tokens
            if self.config.seed is not None:
                body["seed"] = self.config.seed

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
            raise ProviderError("No choices returned from OpenAI Chat API")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        reasoning_content = message.get("reasoning_content")

        # Usage & caching details
        usage_data = res_json.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        prompt_details = usage_data.get("prompt_tokens_details", {})
        cached_tokens = prompt_details.get("cached_tokens", 0)

        comp_details = usage_data.get("completion_tokens_details", {})
        reasoning_tokens = comp_details.get("reasoning_tokens", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        metadata = {
            "finish_reason": choice.get("finish_reason"),
            "model": res_json.get("model"),
            "system_fingerprint": res_json.get("system_fingerprint"),
            "request_id": response.headers.get("x-request-id"),
        }

        return ProviderResponse(
            content=content,
            thinking=reasoning_content,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

    def _is_reasoning_model(self) -> bool:
        """Check if model belongs to the o1 / o3 reasoning series."""
        m = self.config.model.lower()
        return m.startswith("o1") or m.startswith("o3") or "deepseek-r1" in m

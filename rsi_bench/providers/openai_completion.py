"""
OpenAI regular text completions provider implementation (/v1/completions).
Handles legacy text generation models and OpenAI-compatible raw completion routes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class OpenAICompletionProvider(BaseProvider):
    """Provider for OpenAI regular Text Completions API (/v1/completions)."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = (
            get_api_key_for_provider("openai_completion", config.api_key)
            or get_api_key_for_provider("openai", config.api_key)
            or get_api_key_for_provider("openai_chat", config.api_key)
        )
        if not self.api_key:
            raise ProviderError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        # Convert multi-turn conversation into structured completion prompt
        prompt_lines: List[str] = []
        if system_prompt:
            prompt_lines.append(f"System: {system_prompt}\n")

        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            prompt_lines.append(f"{role_label}: {msg.content}")

        prompt_lines.append("Assistant:")
        formatted_prompt = "\n".join(prompt_lines)

        body: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": formatted_prompt,
        }

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
            raise ProviderError(f"No choices returned from OpenAI Completions API: {res_json}")

        choice = choices[0]
        content = choice.get("text", "") or ""

        # Usage
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
            "model": res_json.get("model", self.config.model),
            "id": res_json.get("id"),
        }

        return ProviderResponse(
            content=content.strip(),
            thinking=None,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

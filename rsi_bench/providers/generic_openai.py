"""
Generic OpenAI-compatible provider implementation.
Works with local runtimes (Ollama, vLLM, LMStudio, LocalAI) and custom OpenAI proxies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class GenericOpenAIProvider(BaseProvider):
    """Provider for any OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        # API key is optional for local servers like Ollama
        self.api_key = get_api_key_for_provider("generic_openai", config.api_key) or "not-needed"
        self.base_url = (config.base_url or "http://localhost:11434/v1").rstrip("/")

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
            msg_dict: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "assistant" and msg.thinking:
                msg_dict["reasoning_content"] = msg.thinking
            formatted_messages.append(msg_dict)

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
            raise ProviderError(f"No choices returned from generic OpenAI endpoint: {res_json}")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        reasoning = message.get("reasoning_content") or message.get("reasoning")

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
            "model": res_json.get("model", self.config.model),
        }

        return ProviderResponse(
            content=content,
            thinking=reasoning,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

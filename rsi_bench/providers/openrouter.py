"""
OpenRouter API provider implementation.
Supports unified access to dozens of models, prompt caching headers, and reasoning extraction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class OpenRouterProvider(BaseProvider):
    """Provider for OpenRouter API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("openrouter", config.api_key)
        if not self.api_key:
            raise ProviderError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://openrouter.ai/api/v1").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/rsi-bench/rsi-bench",
            "X-Title": "RSI-Bench",
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            msg_dict: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.role == "assistant" and msg.thinking:
                msg_dict["reasoning"] = msg.thinking
            formatted_messages.append(msg_dict)

        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
        }

        if self.config.enable_thinking:
            body["include_reasoning"] = True
            # OpenRouter requires that ONLY ONE of "effort" and "max_tokens" is specified
            if self.config.thinking_level:
                effort = self.config.thinking_level.lower()
                if effort in ("max", "xhigh"):
                    effort = "high"
                elif effort not in ("high", "medium", "low"):
                    effort = "medium"
                body["reasoning"] = {"effort": effort}
            elif self.config.thinking_budget:
                body["reasoning"] = {"max_tokens": self.config.thinking_budget}
            else:
                body["reasoning"] = {"effort": "medium"}

        if self.config.temperature is not None:
            body["temperature"] = self.config.temperature

        if self.config.max_tokens:
            body["max_tokens"] = self.config.max_tokens

        body.update(self.config.extra_body)

        try:
            response = self._execute_with_retry(
                method="POST",
                url=url,
                headers=headers,
                json_body=body,
            )
        except ProviderError as pe:
            # If model does not support reasoning parameters, retry cleanly without reasoning
            if (
                (body.get("include_reasoning") or body.get("reasoning"))
                and pe.status_code == 400
                and "reasoning" in (pe.response_body or "").lower()
            ):
                fallback_body = dict(body)
                fallback_body.pop("include_reasoning", None)
                fallback_body.pop("reasoning", None)
                response = self._execute_with_retry(
                    method="POST",
                    url=url,
                    headers=headers,
                    json_body=fallback_body,
                )
            else:
                raise

        res_json = response.json()
        choices = res_json.get("choices", [])
        if not choices:
            raise ProviderError(f"No choices returned from OpenRouter API: {res_json}")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        reasoning = message.get("reasoning") or message.get("reasoning_content")

        # Usage
        usage_data = res_json.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        # Cached tokens
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
            "provider": res_json.get("provider"),
        }

        return ProviderResponse(
            content=content,
            thinking=reasoning,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

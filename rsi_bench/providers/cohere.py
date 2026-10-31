"""
Cohere V2 Chat API provider implementation (/v2/chat).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class CohereProvider(BaseProvider):
    """Provider for Cohere V2 Chat API."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("cohere", config.api_key)
        if not self.api_key:
            raise ProviderError("Cohere API key is required. Set COHERE_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.cohere.com/v2").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/chat"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

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
        message_obj = res_json.get("message", {})
        content_items = message_obj.get("content", [])

        texts: List[str] = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)

        content = "".join(texts).strip()

        usage_data = res_json.get("usage", {}).get("tokens", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        metadata = {
            "finish_reason": res_json.get("finish_reason"),
            "response_id": res_json.get("id"),
        }

        return ProviderResponse(
            content=content,
            thinking=None,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

"""
OpenAI Responses API provider implementation (/v1/responses).
Supports multi-turn input items, reasoning configuration, and response output extraction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.config import get_api_key_for_provider
from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.base import BaseProvider, ProviderError


class OpenAIResponsesProvider(BaseProvider):
    """Provider for OpenAI Responses API (/v1/responses)."""

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.api_key = get_api_key_for_provider("openai_responses", config.api_key)
        if not self.api_key:
            raise ProviderError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        # Convert messages to responses input format
        input_items: List[Dict[str, Any]] = []
        for msg in messages:
            input_items.append({
                "role": msg.role,
                "content": msg.content,
            })

        body: Dict[str, Any] = {
            "model": self.config.model,
            "input": input_items,
        }

        if system_prompt:
            body["instructions"] = system_prompt

        if self.config.enable_thinking:
            body["reasoning"] = {"effort": "medium"}

        if self.config.temperature is not None and not self.config.enable_thinking:
            body["temperature"] = self.config.temperature

        body.update(self.config.extra_body)

        response = self._execute_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body=body,
        )

        res_json = response.json()

        # Parse Responses API output
        # Output items can include type="message", type="reasoning"
        output_items = res_json.get("output", [])
        content_parts: List[str] = []
        reasoning_parts: List[str] = []

        for item in output_items:
            item_type = item.get("type")
            if item_type == "message":
                item_content = item.get("content", [])
                if isinstance(item_content, list):
                    for part in item_content:
                        if isinstance(part, dict):
                            if part.get("type") in ("output_text", "text"):
                                content_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            content_parts.append(part)
                elif isinstance(item_content, str):
                    content_parts.append(item_content)
            elif item_type == "reasoning":
                # Reasoning content
                reasoning_content = item.get("content") or item.get("summary")
                if isinstance(reasoning_content, list):
                    for r_part in reasoning_content:
                        if isinstance(r_part, dict) and "text" in r_part:
                            reasoning_parts.append(r_part["text"])
                        elif isinstance(r_part, str):
                            reasoning_parts.append(r_part)
                elif isinstance(reasoning_content, str):
                    reasoning_parts.append(reasoning_content)

        # Fallback if output was direct string or choices (in case endpoint proxy returns chat-like structure)
        if not content_parts and "output_text" in res_json:
            content_parts.append(res_json["output_text"])
        elif not content_parts and "choices" in res_json:
            choice_msg = res_json["choices"][0].get("message", {})
            content_parts.append(choice_msg.get("content", ""))
            if choice_msg.get("reasoning_content"):
                reasoning_parts.append(choice_msg.get("reasoning_content"))

        content = "".join(content_parts).strip()
        thinking = "\n\n".join(reasoning_parts).strip() if reasoning_parts else None

        # Usage
        usage_data = res_json.get("usage", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        in_details = usage_data.get("input_token_details", {})
        cached_tokens = in_details.get("cached_tokens", 0)

        out_details = usage_data.get("output_token_details", {})
        reasoning_tokens = out_details.get("reasoning_tokens", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        metadata = {
            "response_id": res_json.get("id"),
            "status": res_json.get("status"),
            "model": res_json.get("model"),
        }

        return ProviderResponse(
            content=content,
            thinking=thinking,
            usage=usage,
            raw_request=body,
            raw_response=res_json,
            metadata=metadata,
        )

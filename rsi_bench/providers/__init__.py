"""
Provider registry and factory for RSI-Bench.
"""

from __future__ import annotations

import random
from typing import Optional, Type
import httpx

from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers.anthropic import AnthropicProvider
from rsi_bench.providers.base import BaseProvider, ProviderError
from rsi_bench.providers.cohere import CohereProvider
from rsi_bench.providers.deepseek import DeepSeekProvider
from rsi_bench.providers.gemini import GeminiProvider
from rsi_bench.providers.gemini_interactions import GeminiInteractionsProvider
from rsi_bench.providers.generic_openai import GenericOpenAIProvider
from rsi_bench.providers.groq import GroqProvider
from rsi_bench.providers.mistral import MistralProvider
from rsi_bench.providers.openai_chat import OpenAIChatProvider
from rsi_bench.providers.openai_completion import OpenAICompletionProvider
from rsi_bench.providers.openai_responses import OpenAIResponsesProvider
from rsi_bench.providers.openrouter import OpenRouterProvider
from rsi_bench.providers.together import TogetherProvider


class MockProvider(BaseProvider):
    """
    Mock LLM provider for deterministic offline testing, CI/CD, and simulation.
    Simulates multi-turn reasoning traces, thinking blocks, and token caching.
    """

    def __init__(self, config: BenchmarkConfig, http_client: Optional[httpx.Client] = None):
        super().__init__(config, http_client)
        self.rng = random.Random(config.seed or 42)
        self.call_count = 0

    def send_turn(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        self.call_count += 1
        num_turns = len(messages)
        val = self.rng.randint(-1000, 1000)

        thinking = None
        if self.config.enable_thinking:
            thinking = f"Step {self.call_count}: Considering turns ({num_turns}). Selected random integer {val}."

        content = str(val)

        # Simulate cache hits on subsequent turns
        cached = 100 * max(0, self.call_count - 1) if self.config.enable_caching else 0
        prompt_tokens = 50 * self.call_count
        completion_tokens = 25

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cached_tokens=cached,
            reasoning_tokens=20 if thinking else 0,
        )

        return ProviderResponse(
            content=content,
            thinking=thinking,
            usage=usage,
            raw_request={"messages_count": len(messages), "mock": True},
            raw_response={"simulated_val": val, "turn": self.call_count},
            metadata={"mock": True, "call_count": self.call_count},
        )


PROVIDER_MAP: dict[str, Type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "gemini": GeminiProvider,
    "gemini_content": GeminiProvider,
    "gemini_interactions": GeminiInteractionsProvider,
    "gemini-interactions": GeminiInteractionsProvider,
    "interactions": GeminiInteractionsProvider,
    "google": GeminiProvider,
    "openai": OpenAIChatProvider,
    "openai_chat": OpenAIChatProvider,
    "openai_responses": OpenAIResponsesProvider,
    "openai_completion": OpenAICompletionProvider,
    "openai_text": OpenAICompletionProvider,
    "completion": OpenAICompletionProvider,
    "deepseek": DeepSeekProvider,
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "together": TogetherProvider,
    "cohere": CohereProvider,
    "generic": GenericOpenAIProvider,
    "generic_openai": GenericOpenAIProvider,
    "ollama": GenericOpenAIProvider,
    "mock": MockProvider,
}


def get_provider(
    provider_name: str,
    config: BenchmarkConfig,
    http_client: Optional[httpx.Client] = None,
) -> BaseProvider:
    """Instantiate and return the appropriate provider instance."""
    normalized = provider_name.strip().lower()
    provider_cls = PROVIDER_MAP.get(normalized)
    if not provider_cls:
        available = ", ".join(sorted(PROVIDER_MAP.keys()))
        raise ProviderError(
            f"Unknown provider '{provider_name}'. Supported providers: {available}"
        )
    return provider_cls(config=config, http_client=http_client)


__all__ = [
    "AnthropicProvider",
    "BaseProvider",
    "CohereProvider",
    "DeepSeekProvider",
    "GeminiInteractionsProvider",
    "GeminiProvider",
    "GenericOpenAIProvider",
    "GroqProvider",
    "MistralProvider",
    "MockProvider",
    "OpenAIChatProvider",
    "OpenAICompletionProvider",
    "OpenAIResponsesProvider",
    "OpenRouterProvider",
    "PROVIDER_MAP",
    "ProviderError",
    "TogetherProvider",
    "get_provider",
]

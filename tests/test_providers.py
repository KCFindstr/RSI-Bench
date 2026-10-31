"""Tests for LLM provider implementations using httpx.MockTransport."""

import json
import pytest
import httpx

from rsi_bench.models import BenchmarkConfig, Message
from rsi_bench.providers import (
    AnthropicProvider,
    CohereProvider,
    DeepSeekProvider,
    GeminiProvider,
    GenericOpenAIProvider,
    GroqProvider,
    MistralProvider,
    OpenAIChatProvider,
    OpenAIResponsesProvider,
    OpenRouterProvider,
    TogetherProvider,
    get_provider,
)


class TestAnthropicProvider:
    def test_anthropic_messages_caching_and_thinking(self):
        recorded_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_request["headers"] = dict(request.headers)
            recorded_request["body"] = json.loads(request.read())
            resp_body = {
                "id": "msg_123",
                "model": "claude-3-7-sonnet-20250219",
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let's generate 42.", "signature": "sig123"},
                    {"type": "text", "text": "42"},
                ],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 150,
                    "output_tokens": 25,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 80,
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="anthropic",
            model="claude-3-7-sonnet-20250219",
            api_key="test-key",
            enable_thinking=True,
            thinking_budget=1024,
            enable_caching=True,
        )
        provider = AnthropicProvider(config=config, http_client=client)

        messages = [
            Message(role="user", content="Turn 1"),
            Message(role="assistant", content="42", thinking="prev thought"),
            Message(role="user", content="Turn 2"),
        ]
        resp = provider.send_turn(messages=messages, system_prompt="You are an RNG.")

        assert resp.content == "42"
        assert resp.thinking == "Let's generate 42."
        assert resp.usage.cached_tokens == 80
        assert resp.usage.cache_creation_tokens == 20
        assert resp.usage.prompt_tokens == 150
        assert resp.usage.completion_tokens == 25

        # Verify caching header was sent
        assert "prompt-caching-2024-07-31" in recorded_request["headers"]["anthropic-beta"]
        # Verify thinking block requested
        assert recorded_request["body"]["thinking"]["budget_tokens"] == 1024


class TestOpenAIChatProvider:
    def test_openai_chat_reasoning_and_cached_tokens(self):
        recorded_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_request["body"] = json.loads(request.read())
            resp_body = {
                "id": "chatcmpl-123",
                "model": "o3-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "777",
                            "reasoning_content": "Thinking step by step...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 80,
                    "completion_tokens": 30,
                    "total_tokens": 110,
                    "prompt_tokens_details": {"cached_tokens": 64},
                    "completion_tokens_details": {"reasoning_tokens": 20},
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openai_chat",
            model="o3-mini",
            api_key="test-key",
            enable_thinking=True,
        )
        provider = OpenAIChatProvider(config=config, http_client=client)

        resp = provider.send_turn(messages=[Message(role="user", content="Generate integer")])

        assert resp.content == "777"
        assert resp.thinking == "Thinking step by step..."
        assert resp.usage.cached_tokens == 64
        assert resp.usage.reasoning_tokens == 20
        assert recorded_request["body"]["reasoning_effort"] == "medium"


class TestOpenAIResponsesProvider:
    def test_openai_responses_format_and_parsing(self):
        def handler(request: httpx.Request) -> httpx.Response:
            resp_body = {
                "id": "resp_999",
                "status": "completed",
                "model": "gpt-4o",
                "output": [
                    {
                        "type": "reasoning",
                        "content": [{"type": "text", "text": "Reasoning about random number"}],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "99"}],
                    },
                ],
                "usage": {
                    "input_tokens": 60,
                    "output_tokens": 15,
                    "total_tokens": 75,
                    "input_token_details": {"cached_tokens": 32},
                    "output_token_details": {"reasoning_tokens": 10},
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openai_responses",
            model="gpt-4o",
            api_key="test-key",
            enable_thinking=True,
        )
        provider = OpenAIResponsesProvider(config=config, http_client=client)

        resp = provider.send_turn(messages=[Message(role="user", content="Generate integer")])

        assert resp.content == "99"
        assert "Reasoning about random number" in (resp.thinking or "")
        assert resp.usage.cached_tokens == 32
        assert resp.usage.reasoning_tokens == 10


class TestGeminiProvider:
    def test_gemini_thought_parts_and_cache(self):
        def handler(request: httpx.Request) -> httpx.Response:
            resp_body = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"text": "Gemini internal reasoning trace.", "thought": True},
                                {"text": "88"},
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 45,
                    "candidatesTokenCount": 18,
                    "totalTokenCount": 63,
                    "cachedContentTokenCount": 25,
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="gemini",
            model="gemini-2.5-flash",
            api_key="test-key",
            enable_thinking=True,
        )
        provider = GeminiProvider(config=config, http_client=client)

        resp = provider.send_turn(messages=[Message(role="user", content="Generate integer")])

        assert resp.content == "88"
        assert resp.thinking == "Gemini internal reasoning trace."
        assert resp.usage.cached_tokens == 25
        assert resp.usage.prompt_tokens == 45


class TestDeepSeekProvider:
    def test_deepseek_reasoning_and_cache_hits(self):
        def handler(request: httpx.Request) -> httpx.Response:
            resp_body = {
                "id": "ds-123",
                "model": "deepseek-reasoner",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "333",
                            "reasoning_content": "DeepSeek R1 thinking trajectory...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 50,
                    "total_tokens": 170,
                    "prompt_cache_hit_tokens": 96,
                    "prompt_cache_miss_tokens": 24,
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="deepseek",
            model="deepseek-reasoner",
            api_key="test-key",
        )
        provider = DeepSeekProvider(config=config, http_client=client)

        resp = provider.send_turn(messages=[Message(role="user", content="Generate integer")])

        assert resp.content == "333"
        assert resp.thinking == "DeepSeek R1 thinking trajectory..."
        assert resp.usage.cached_tokens == 96


class TestOpenRouterProvider:
    def test_openrouter_reasoning(self):
        def handler(request: httpx.Request) -> httpx.Response:
            resp_body = {
                "id": "or-123",
                "model": "deepseek/deepseek-r1",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "555",
                            "reasoning": "OpenRouter forwarded reasoning...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 40,
                    "total_tokens": 140,
                    "prompt_tokens_details": {"cached_tokens": 50},
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openrouter",
            model="deepseek/deepseek-r1",
            api_key="test-key",
            enable_thinking=True,
        )
        provider = OpenRouterProvider(config=config, http_client=client)

        resp = provider.send_turn(messages=[Message(role="user", content="Generate integer")])

        assert resp.content == "555"
        assert resp.thinking == "OpenRouter forwarded reasoning..."
        assert resp.usage.cached_tokens == 50


class TestOtherProviders:
    def test_groq(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "12", "reasoning": "groq think"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="groq", model="test-model", api_key="k")
        resp = GroqProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "12"
        assert resp.thinking == "groq think"

    def test_mistral(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "7"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="mistral", model="test-model", api_key="k")
        resp = MistralProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "7"

    def test_together(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "99", "reasoning_content": "think"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="together", model="test-model", api_key="k")
        resp = TogetherProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "99"
        assert resp.thinking == "think"

    def test_cohere(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "message": {"content": [{"type": "text", "text": "42"}]},
                "usage": {"tokens": {"input_tokens": 10, "output_tokens": 5}},
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="cohere", model="test-model", api_key="k")
        resp = CohereProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "42"

    def test_generic_openai(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": "100"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="generic_openai", model="test-model")
        resp = GenericOpenAIProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "100"

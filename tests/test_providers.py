"""Tests for LLM provider implementations using httpx.MockTransport."""

import json
import pytest
import httpx

from rsi_bench.models import BenchmarkConfig, Message
from rsi_bench.providers import (
    AnthropicProvider,
    CohereProvider,
    DeepSeekProvider,
    GeminiInteractionsProvider,
    GeminiProvider,
    GenericOpenAIProvider,
    GroqProvider,
    MistralProvider,
    OpenAIChatProvider,
    OpenAICompletionProvider,
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

    def test_anthropic_turn1_sets_cache_control(self):
        recorded_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_request["body"] = json.loads(request.read())
            return httpx.Response(200, json={
                "id": "msg_t1",
                "model": "claude-3-7-sonnet",
                "content": [{"type": "text", "text": "7"}],
                "usage": {"input_tokens": 20, "output_tokens": 5},
            })

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="anthropic",
            model="claude-3-7-sonnet",
            api_key="test-key",
            enable_caching=True,
        )
        provider = AnthropicProvider(config=config, http_client=client)

        provider.send_turn([Message(role="user", content="Turn 1 prompt")])

        # On Turn 1, the user message content block must have cache_control
        user_block = recorded_request["body"]["messages"][0]["content"][0]
        assert user_block.get("cache_control") == {"type": "ephemeral"}


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


class TestOpenAICompletionProvider:
    def test_openai_completion_route(self):
        recorded_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_request["body"] = json.loads(request.read())
            resp_body = {
                "id": "cmpl-456",
                "model": "gpt-3.5-turbo-instruct",
                "choices": [
                    {
                        "text": " 42\n",
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 5,
                    "total_tokens": 35,
                    "prompt_tokens_details": {"cached_tokens": 15},
                },
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openai_completion",
            model="gpt-3.5-turbo-instruct",
            api_key="test-key",
        )
        provider = OpenAICompletionProvider(config=config, http_client=client)

        resp = provider.send_turn(
            messages=[
                Message(role="user", content="Turn 1"),
                Message(role="assistant", content="10"),
                Message(role="user", content="Turn 2"),
            ],
            system_prompt="You are an RNG.",
        )

        assert resp.content == "42"
        assert resp.usage.prompt_tokens == 30
        assert resp.usage.completion_tokens == 5
        assert resp.usage.cached_tokens == 15
        assert "System: You are an RNG." in recorded_request["body"]["prompt"]
        assert "User: Turn 2" in recorded_request["body"]["prompt"]


class TestGeminiInteractionsProvider:
    def test_gemini_interactions_multiturn_state_and_thinking(self):
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.read())
            recorded_requests.append(body)

            turn = len(recorded_requests)
            if turn == 1:
                resp_body = {
                    "id": "interaction_turn_1",
                    "model": "gemini-2.5-flash",
                    "status": "completed",
                    "steps": [
                        {"type": "thought", "text": "Interactions turn 1 reasoning trace."},
                        {"type": "model_output", "text": "42"},
                    ],
                    "usage": {
                        "total_input_tokens": 35,
                        "total_output_tokens": 12,
                        "total_thought_tokens": 8,
                        "total_tokens": 47,
                        "cached_tokens": 0,
                    },
                }
            else:
                resp_body = {
                    "id": "interaction_turn_2",
                    "model": "gemini-2.5-flash",
                    "status": "completed",
                    "steps": [
                        {"type": "thought", "text": "Interactions turn 2 continuation reasoning."},
                        {"type": "model_output", "text": "99"},
                    ],
                    "usage": {
                        "total_input_tokens": 45,
                        "total_output_tokens": 14,
                        "total_thought_tokens": 10,
                        "total_tokens": 59,
                        "cached_tokens": 25,
                    },
                }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="gemini_interactions",
            model="gemini-2.5-flash",
            api_key="test-key",
            enable_thinking=True,
            thinking_budget=1024,
        )
        provider = GeminiInteractionsProvider(config=config, http_client=client)

        # Turn 1
        resp1 = provider.send_turn(messages=[Message(role="user", content="Generate integer turn 1")])
        assert resp1.content == "42"
        assert resp1.thinking == "Interactions turn 1 reasoning trace."
        assert resp1.usage.reasoning_tokens == 8
        assert resp1.metadata["interaction_id"] == "interaction_turn_1"
        assert "previous_interaction_id" not in recorded_requests[0]
        assert recorded_requests[0]["store"] is True

        # Turn 2
        messages_turn2 = [
            Message(role="user", content="Generate integer turn 1"),
            Message(role="assistant", content="42", thinking="Interactions turn 1 reasoning trace."),
            Message(role="user", content="Generate integer turn 2"),
        ]
        resp2 = provider.send_turn(messages=messages_turn2)
        assert resp2.content == "99"
        assert resp2.thinking == "Interactions turn 2 continuation reasoning."
        assert resp2.usage.cached_tokens == 25
        assert resp2.usage.reasoning_tokens == 10
        # Verify previous_interaction_id was sent for server-side state linking
        assert recorded_requests[1]["previous_interaction_id"] == "interaction_turn_1"


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
                    "thoughtTokenCount": 10,
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
        assert resp.usage.reasoning_tokens == 10


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
                    "completion_tokens_details": {"reasoning_tokens": 40},
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
        assert resp.usage.reasoning_tokens == 40


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
                    "completion_tokens_details": {"reasoning_tokens": 25},
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
        assert resp.usage.reasoning_tokens == 25

    def test_openrouter_effort_mutual_exclusion(self):
        recorded_request = {}

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_request["body"] = json.loads(request.read())
            resp_body = {
                "id": "or-456",
                "model": "openai/o1",
                "choices": [{"message": {"role": "assistant", "content": "100"}}],
            }
            return httpx.Response(200, json=resp_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openrouter",
            model="openai/o1",
            api_key="test-key",
            enable_thinking=True,
            thinking_level="max",
            thinking_budget=32000,
        )
        provider = OpenRouterProvider(config=config, http_client=client)
        resp = provider.send_turn(messages=[Message(role="user", content="Generate")])
        assert resp.content == "100"

        # Verify ONLY effort is sent, NOT max_tokens
        reasoning = recorded_request["body"].get("reasoning", {})
        assert "effort" in reasoning
        assert "max_tokens" not in reasoning
        assert reasoning["effort"] == "high"

    def test_openrouter_fallback_on_unsupported_reasoning(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.read())
            calls.append(body)
            if len(calls) == 1:
                # First call fails because model doesn't support reasoning
                return httpx.Response(
                    400,
                    text='{"error":{"message":"reasoning is not supported for this model","code":400}}',
                )
            # Second call succeeds without reasoning
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "42"}}]},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(
            provider="openrouter",
            model="openai/gpt-4o",
            api_key="test-key",
            enable_thinking=True,
            thinking_level="max",
        )
        provider = OpenRouterProvider(config=config, http_client=client)
        resp = provider.send_turn(messages=[Message(role="user", content="Generate")])
        assert resp.content == "42"
        assert len(calls) == 2
        assert "reasoning" in calls[0]
        assert "reasoning" not in calls[1]
        assert "include_reasoning" not in calls[1]


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
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "completion_tokens_details": {"reasoning_tokens": 3},
                    "prompt_tokens_details": {"cached_tokens": 2},
                },
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="together", model="test-model", api_key="k")
        resp = TogetherProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "99"
        assert resp.thinking == "think"
        assert resp.usage.reasoning_tokens == 3
        assert resp.usage.cached_tokens == 2

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
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "completion_tokens_details": {"reasoning_tokens": 4},
                },
            })
        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = BenchmarkConfig(provider="generic_openai", model="test-model")
        resp = GenericOpenAIProvider(config, client).send_turn([Message(role="user", content="hi")])
        assert resp.content == "100"
        assert resp.usage.reasoning_tokens == 4

    def test_provider_factory_routing(self):
        config = BenchmarkConfig(provider="gemini_interactions", model="gemini-2.5-flash", api_key="k")
        p = get_provider("gemini_interactions", config)
        assert isinstance(p, GeminiInteractionsProvider)

        config2 = BenchmarkConfig(provider="openai_completion", model="gpt-3.5-turbo-instruct", api_key="k")
        p2 = get_provider("openai_completion", config2)
        assert isinstance(p2, OpenAICompletionProvider)

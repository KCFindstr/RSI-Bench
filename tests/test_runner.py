"""Unit tests for BenchmarkRunner multi-turn execution and trace logging."""

import tempfile
import pytest

from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage
from rsi_bench.providers import BaseProvider, MockProvider
from rsi_bench.runner import BenchmarkRunner
from rsi_bench.storage import StorageManager


class DummyMultiTurnProvider(BaseProvider):
    """Custom provider that validates multi-turn conversation growth."""
    def __init__(self, config: BenchmarkConfig):
        super().__init__(config)
        self.received_messages_history = []

    def send_turn(self, messages, system_prompt=None):
        self.received_messages_history.append(list(messages))
        turn_num = (len(messages) + 1) // 2
        # Return valid integer with thinking
        return ProviderResponse(
            content=f"**{turn_num * 10}**",
            thinking=f"Turn {turn_num} thinking trace",
            usage=TokenUsage(prompt_tokens=20 * turn_num, completion_tokens=5, cached_tokens=10 * (turn_num - 1)),
        )


class TestBenchmarkRunner:
    def test_multiturn_conversation_growth_and_traces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BenchmarkConfig(
                provider="custom",
                model="test-model",
                num_turns=3,
                prompt="Generate a random integer. Do NOT output anything else.",
                enable_thinking=True,
            )
            storage = StorageManager(output_dir=tmpdir)
            provider = DummyMultiTurnProvider(config)
            runner = BenchmarkRunner(config=config, storage_manager=storage, provider=provider)

            result = runner.run()

            assert result.num_turns_requested == 3
            assert result.num_turns_completed == 3
            assert result.all_valid is True
            assert result.parsed_integers == [10, 20, 30]

            # Verify conversation history was passed properly in multi-turn
            # Turn 1: 1 message (user)
            assert len(provider.received_messages_history[0]) == 1
            assert provider.received_messages_history[0][0].role == "user"
            assert provider.received_messages_history[0][0].content == "Generate a random integer. Do NOT output anything else."

            # Turn 2: 3 messages (user, assistant, user)
            assert len(provider.received_messages_history[1]) == 3
            assert provider.received_messages_history[1][1].role == "assistant"
            assert provider.received_messages_history[1][1].content == "**10**"

            # Turn 3: 5 messages (user, assistant, user, assistant, user)
            assert len(provider.received_messages_history[2]) == 5

            # Verify traces recorded
            assert len(result.turns) == 3
            for i, turn in enumerate(result.turns, 1):
                assert turn.turn_index == i
                assert turn.prompt == "Generate a random integer. Do NOT output anything else."
                assert turn.parsed_integer == i * 10
                assert turn.parse_success is True
                assert turn.thinking_trace == f"Turn {i} thinking trace"
                assert turn.token_usage.cached_tokens == 10 * (i - 1)

            # Check aggregate token usage
            assert result.total_usage.prompt_tokens == 20 + 40 + 60
            assert result.total_usage.cached_tokens == 0 + 10 + 20

    def test_runner_with_mock_provider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BenchmarkConfig(
                provider="mock",
                model="mock-v1",
                num_turns=4,
                seed=123,
            )
            storage = StorageManager(output_dir=tmpdir)
            runner = BenchmarkRunner(config=config, storage_manager=storage)

            result = runner.run()

            assert result.num_turns_requested == 4
            assert result.num_turns_completed == 4
            assert result.all_valid is True
            assert len(result.parsed_integers) == 4
            assert all(isinstance(x, int) for x in result.parsed_integers)
            assert all(t.thinking_trace is not None for t in result.turns)

    def test_runner_recovers_and_records_provider_error(self):
        class FailingProvider(BaseProvider):
            def send_turn(self, messages, system_prompt=None):
                if len(messages) > 1:
                    raise RuntimeError("API quota exhausted on turn 2")
                return ProviderResponse(content="100")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = BenchmarkConfig(provider="fail", model="m", num_turns=3)
            storage = StorageManager(output_dir=tmpdir)
            provider = FailingProvider(config)
            runner = BenchmarkRunner(config=config, storage_manager=storage, provider=provider)

            result = runner.run()

            assert result.num_turns_completed == 2
            assert result.all_valid is False
            assert "API quota exhausted on turn 2" in (result.error or "")
            assert result.turns[0].parse_success is True
            assert result.turns[0].parsed_integer == 100
            assert result.turns[1].parse_success is False
            assert "API quota exhausted" in (result.turns[1].parse_error or "")

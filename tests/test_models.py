"""Unit tests for models and token accounting."""

import pytest
from rsi_bench.models import BenchmarkConfig, BenchmarkResult, Message, TokenUsage, TurnTrace


def test_token_usage_addition():
    u1 = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30, cached_tokens=5, reasoning_tokens=8)
    u2 = TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40, cached_tokens=10, reasoning_tokens=12)

    total = u1.add(u2)
    assert total.prompt_tokens == 25
    assert total.completion_tokens == 45
    assert total.total_tokens == 70
    assert total.cached_tokens == 15
    assert total.reasoning_tokens == 20


def test_benchmark_result_serialization():
    res = BenchmarkResult(
        run_id="test1234",
        provider="anthropic",
        model="claude-3-7-sonnet",
        num_turns_requested=2,
        num_turns_completed=2,
        parsed_integers=[42, 100],
        all_valid=True,
        valid_turns_count=2,
        turns=[
            TurnTrace(
                turn_index=1,
                prompt="Generate integer",
                raw_response_text="42",
                thinking_trace="thinking step",
                parsed_integer=42,
                parse_success=True,
                latency_ms=120.0,
            )
        ],
    )

    data = res.model_dump()
    assert data["run_id"] == "test1234"
    assert data["parsed_integers"] == [42, 100]
    assert data["turns"][0]["parsed_integer"] == 42


def test_batch_models_serialization():
    from rsi_bench.models import BatchBenchmarkResult, BatchConfig, BatchRunItem

    cfg = BatchConfig(
        output_dir="custom_dir",
        defaults={"num_turns": 4},
        api_keys={"openai": "sk-123"},
        runs=[
            BatchRunItem(provider="mock", name="run-1", tags=["fast", "mock"]),
        ],
    )
    dumped_cfg = cfg.model_dump()
    loaded_cfg = BatchConfig(**dumped_cfg)
    assert loaded_cfg.output_dir == "custom_dir"
    assert loaded_cfg.runs[0].tags == ["fast", "mock"]

    batch_res = BatchBenchmarkResult(
        batch_id="batch_xyz",
        total_runs=1,
        completed_runs=1,
        successful_runs=1,
        failed_runs=0,
        all_successful=True,
    )
    dumped_res = batch_res.model_dump()
    loaded_res = BatchBenchmarkResult(**dumped_res)
    assert loaded_res.batch_id == "batch_xyz"
    assert loaded_res.all_successful is True

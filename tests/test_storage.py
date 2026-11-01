"""Unit tests for StorageManager."""

import csv
import json
import tempfile
from pathlib import Path
import pytest

from rsi_bench.models import BenchmarkResult, TokenUsage, TurnTrace
from rsi_bench.storage import StorageManager


def test_storage_json_and_markdown_and_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = StorageManager(output_dir=tmpdir)

        result = BenchmarkResult(
            run_id="run_abc123",
            provider="openai_chat",
            model="gpt-4o",
            num_turns_requested=2,
            num_turns_completed=2,
            parsed_integers=[42, -5],
            all_valid=True,
            valid_turns_count=2,
            total_latency_ms=450.5,
            avg_turn_latency_ms=225.25,
            total_usage=TokenUsage(prompt_tokens=100, completion_tokens=20, cached_tokens=50),
            turns=[
                TurnTrace(
                    turn_index=1,
                    prompt="Generate a random integer. Do NOT output anything else.",
                    raw_response_text="42",
                    thinking_trace="Reasoning 1",
                    parsed_integer=42,
                    parse_success=True,
                    latency_ms=200.0,
                    token_usage=TokenUsage(prompt_tokens=50, completion_tokens=10),
                ),
                TurnTrace(
                    turn_index=2,
                    prompt="Generate a random integer. Do NOT output anything else.",
                    raw_response_text="-5",
                    thinking_trace="Reasoning 2",
                    parsed_integer=-5,
                    parse_success=True,
                    latency_ms=250.5,
                    token_usage=TokenUsage(prompt_tokens=50, completion_tokens=10, cached_tokens=50),
                ),
            ],
            config={"temperature": 1.0},
        )

        saved_path = storage.save_result(result)
        assert saved_path.exists()

        # Check JSON trace
        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["run_id"] == "run_abc123"
        assert data["parsed_integers"] == [42, -5]
        assert len(data["turns"]) == 2
        assert data["turns"][0]["thinking_trace"] == "Reasoning 1"

        # Check Markdown file
        md_path = storage.traces_dir / f"{result.provider}_{result.model.replace('/', '_')}_{result.run_id}.md"
        assert md_path.exists()
        md_text = md_path.read_text(encoding="utf-8")
        assert "RSI-Bench Run Report" in md_text
        assert "42" in md_text
        assert "-5" in md_text
        assert "Integer Sum:" in md_text
        assert "Integer Mean / Turn:" in md_text
        assert "Reasoning 1" in md_text

        # Check CSV
        csv_path = Path(tmpdir) / "benchmark_summary.csv"
        assert csv_path.exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["run_id"] == "run_abc123"
        assert reader[0]["provider"] == "openai_chat"
        assert reader[0]["all_valid"] == "True"
        assert reader[0]["parsed_integers"] == "[42, -5]"
        assert reader[0]["sum_integers"] == "37"
        assert reader[0]["avg_integers"] == "18.5"
        assert reader[0]["total_cached_tokens"] == "50"

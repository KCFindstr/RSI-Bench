"""
Storage manager for RSI-Bench.
Saves structured JSON traces, human-readable Markdown summaries, and aggregate CSV logs.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from rsi_bench.models import BenchmarkResult


class StorageManager:
    """Manages writing traces, parsed outputs, and benchmark reports."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir = self.output_dir / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, result: BenchmarkResult) -> Path:
        """
        Saves the complete benchmark result with all turn traces to a JSON file.
        Returns the path to the saved JSON file.
        """
        filename = f"{result.provider}_{result.model.replace('/', '_')}_{result.run_id}.json"
        target_path = self.traces_dir / filename

        # Serialize Pydantic result model
        data = result.model_dump()

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Also write the Markdown summary and append to CSV
        self.save_markdown_summary(result)
        self.append_to_summary_csv(result)

        return target_path

    def save_markdown_summary(self, result: BenchmarkResult) -> Path:
        """Generates and writes a readable Markdown report of the run."""
        filename = f"{result.provider}_{result.model.replace('/', '_')}_{result.run_id}.md"
        target_path = self.traces_dir / filename

        md_lines = [
            f"# RSI-Bench Run Report: {result.provider} / {result.model}",
            "",
            f"- **Run ID:** `{result.run_id}`",
            f"- **Timestamp:** `{result.timestamp}`",
            f"- **Turns Completed:** {result.num_turns_completed} / {result.num_turns_requested}",
            f"- **All Outputs Valid Integers:** {'✅ Yes' if result.all_valid else '❌ No'}",
            f"- **Parsed Final Integers:** `{result.parsed_integers}`",
            f"- **Total Latency:** {result.total_latency_ms:.1f} ms (avg {result.avg_turn_latency_ms:.1f} ms/turn)",
            f"- **Total Tokens:** {result.total_usage.total_tokens} (prompt: {result.total_usage.prompt_tokens}, completion: {result.total_usage.completion_tokens})",
            f"- **Cached Tokens:** {result.total_usage.cached_tokens}",
            f"- **Reasoning/Thinking Tokens:** {result.total_usage.reasoning_tokens}",
            "",
            "## Turn-by-Turn Breakdown",
            "",
            "| Turn | Parsed Int | Valid | Latency (ms) | Tokens (Prompt/Comp/Cached) | Thinking Recorded |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for turn in result.turns:
            has_thinking = "Yes" if turn.thinking_trace else "No"
            valid_mark = "✅" if turn.parse_success else "❌"
            int_repr = str(turn.parsed_integer) if turn.parsed_integer is not None else "None"
            usage_str = f"{turn.token_usage.prompt_tokens}/{turn.token_usage.completion_tokens}/{turn.token_usage.cached_tokens}"
            md_lines.append(
                f"| {turn.turn_index} | `{int_repr}` | {valid_mark} | {turn.latency_ms:.1f} | {usage_str} | {has_thinking} |"
            )

        md_lines.append("")
        md_lines.append("## Detailed Traces & Thinking")
        md_lines.append("")

        for turn in result.turns:
            md_lines.append(f"### Turn {turn.turn_index}")
            md_lines.append(f"**Prompt:** `{turn.prompt}`")
            md_lines.append(f"**Parsed Integer:** `{turn.parsed_integer}` (Success: {turn.parse_success})")
            if turn.parse_error:
                md_lines.append(f"**Parse Error:** `{turn.parse_error}`")

            if turn.thinking_trace:
                md_lines.append("")
                md_lines.append("<details><summary>🧠 <b>Thinking Trace</b></summary>")
                md_lines.append("")
                md_lines.append("```text")
                md_lines.append(turn.thinking_trace)
                md_lines.append("```")
                md_lines.append("</details>")
                md_lines.append("")

            md_lines.append("")
            md_lines.append("<details><summary>💬 <b>Raw Response</b></summary>")
            md_lines.append("")
            md_lines.append("```text")
            md_lines.append(turn.raw_response_text)
            md_lines.append("```")
            md_lines.append("</details>")
            md_lines.append("")

        content = "\n".join(md_lines)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        return target_path

    def append_to_summary_csv(self, result: BenchmarkResult) -> Path:
        """Appends run summary to a centralized CSV file."""
        csv_path = self.output_dir / "benchmark_summary.csv"
        file_exists = csv_path.exists()

        fieldnames = [
            "run_id",
            "timestamp",
            "provider",
            "model",
            "num_turns_requested",
            "num_turns_completed",
            "all_valid",
            "valid_turns_count",
            "parsed_integers",
            "total_latency_ms",
            "avg_turn_latency_ms",
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_cached_tokens",
            "total_reasoning_tokens",
            "error",
        ]

        row = {
            "run_id": result.run_id,
            "timestamp": result.timestamp,
            "provider": result.provider,
            "model": result.model,
            "num_turns_requested": result.num_turns_requested,
            "num_turns_completed": result.num_turns_completed,
            "all_valid": result.all_valid,
            "valid_turns_count": result.valid_turns_count,
            "parsed_integers": json.dumps(result.parsed_integers),
            "total_latency_ms": round(result.total_latency_ms, 2),
            "avg_turn_latency_ms": round(result.avg_turn_latency_ms, 2),
            "total_prompt_tokens": result.total_usage.prompt_tokens,
            "total_completion_tokens": result.total_usage.completion_tokens,
            "total_cached_tokens": result.total_usage.cached_tokens,
            "total_reasoning_tokens": result.total_usage.reasoning_tokens,
            "error": result.error or "",
        }

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        return csv_path

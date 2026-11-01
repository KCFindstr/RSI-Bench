"""
Storage manager for RSI-Bench.
Saves structured JSON traces, human-readable Markdown summaries, and aggregate CSV logs.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Optional

from rsi_bench.models import BatchBenchmarkResult, BenchmarkResult


def sanitize_filename_component(text: str) -> str:
    """Sanitize provider and model identifiers for cross-platform safe filenames."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)


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
        safe_provider = sanitize_filename_component(result.provider)
        safe_model = sanitize_filename_component(result.model)
        filename = f"{safe_provider}_{safe_model}_{result.run_id}.json"
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
        safe_provider = sanitize_filename_component(result.provider)
        safe_model = sanitize_filename_component(result.model)
        filename = f"{safe_provider}_{safe_model}_{result.run_id}.md"
        target_path = self.traces_dir / filename

        md_lines = [
            f"# RSI-Bench Run Report: {result.provider} / {result.model}",
            "",
            f"- **Run ID:** `{result.run_id}`",
            f"- **Timestamp:** `{result.timestamp}`",
            f"- **Turns Completed:** {result.num_turns_completed} / {result.num_turns_requested}",
            f"- **All Outputs Valid Integers:** {'✅ Yes' if result.all_valid else '❌ No'}",
        ]
        if result.error:
            md_lines.append(f"- **Error:** `{result.error}`")
        md_lines.extend([
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
        ])

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

    def save_batch_result(self, batch_result: BatchBenchmarkResult) -> tuple[Path, Path]:
        """
        Saves the batch benchmark result JSON and Markdown report.
        Returns a tuple of (json_path, markdown_path).
        """
        json_path = self.output_dir / f"batch_{batch_result.batch_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(batch_result.model_dump(), f, indent=2, ensure_ascii=False)

        md_path = self.save_batch_markdown_summary(batch_result)
        return json_path, md_path

    def save_batch_markdown_summary(self, batch_result: BatchBenchmarkResult) -> Path:
        """Generates and writes a readable aggregate Markdown report of the batch run."""
        md_path = self.output_dir / f"batch_{batch_result.batch_id}.md"

        all_ok = "✅ Yes" if batch_result.all_successful else "❌ No"
        lines = [
            f"# RSI-Bench Batch Execution Report",
            "",
            f"- **Batch ID:** `{batch_result.batch_id}`",
            f"- **Timestamp:** `{batch_result.timestamp}`",
            f"- **Total Runs:** {batch_result.total_runs} ({batch_result.successful_runs} passed, {batch_result.failed_runs} failed)",
            f"- **All Runs Successful:** {all_ok}",
            f"- **Total Latency:** {batch_result.total_latency_ms:.1f} ms",
            f"- **Total Tokens:** {batch_result.total_usage.total_tokens} (Prompt: {batch_result.total_usage.prompt_tokens}, Completion: {batch_result.total_usage.completion_tokens})",
            f"- **Total Cached Tokens:** {batch_result.total_usage.cached_tokens}",
            f"- **Total Reasoning Tokens:** {batch_result.total_usage.reasoning_tokens}",
            "",
            "## Runs Summary Table",
            "",
            "| # | Run Name | Provider | Model | Turns | Valid | Integers | Latency (ms) | Tokens (P/C/Cached/Reasoning) | Status |",
            "| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for idx, res in enumerate(batch_result.results, start=1):
            name = res.config.get("name") or f"{res.provider}_{res.model}"
            status = "✅ PASS" if res.all_valid else "❌ FAIL"
            valid_mark = "✅" if res.all_valid else "❌"
            ints_str = f"`{res.parsed_integers}`" if res.parsed_integers else "`[]`"
            usage_str = f"{res.total_usage.prompt_tokens}/{res.total_usage.completion_tokens}/{res.total_usage.cached_tokens}/{res.total_usage.reasoning_tokens}"
            lines.append(
                f"| {idx} | `{name}` | {res.provider} | {res.model} | {res.num_turns_completed}/{res.num_turns_requested} | {valid_mark} | {ints_str} | {res.total_latency_ms:.1f} | {usage_str} | {status} |"
            )

        lines.append("")
        lines.append("## Individual Run Reports")
        lines.append("")

        for idx, res in enumerate(batch_result.results, start=1):
            name = res.config.get("name") or f"{res.provider}_{res.model}"
            safe_prov = sanitize_filename_component(res.provider)
            safe_model = sanitize_filename_component(res.model)
            trace_json = f"traces/{safe_prov}_{safe_model}_{res.run_id}.json"
            trace_md = f"traces/{safe_prov}_{safe_model}_{res.run_id}.md"
            status_str = "Passed" if res.all_valid else "Failed"

            lines.append(f"### {idx}. {name} (`{res.provider}` / `{res.model}`)")
            lines.append(f"- **Status:** {status_str}")
            lines.append(f"- **Run ID:** `{res.run_id}`")
            lines.append(f"- **Parsed Integers:** `{res.parsed_integers}`")
            lines.append(f"- **Latency:** {res.total_latency_ms:.1f} ms")
            if res.error:
                lines.append(f"- **Error:** `{res.error}`")
            lines.append(f"- **Trace JSON:** [`{trace_json}`]({trace_json})")
            lines.append(f"- **Run Report:** [`{trace_md}`]({trace_md})")
            lines.append("")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return md_path

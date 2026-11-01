"""
CLI formatting and presentation utilities.
Handles Windows console encoding and ANSI colors safely.
"""

from __future__ import annotations

import sys
from typing import Any, List, Optional
from rsi_bench.models import BatchBenchmarkResult, BenchmarkResult, TurnTrace

# Ensure UTF-8 output on Windows if possible
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Simple ANSI colors that work across modern terminals
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def colorize(text: str, color_code: str) -> str:
    """Apply ANSI styling if stdout is a tty."""
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        return f"{color_code}{text}{RESET}"
    return text


def print_banner() -> None:
    banner = f"""
{BOLD}{CYAN}======================================================================
  ____  ____ ___       ____                  _     
 |  _ \\/ ___|_ _|     | __ )  ___ _ __   ___| |__  
 | |_) \\___ \\| | _____|  _ \\ / _ \\ '_ \\ / __| '_ \\ 
 |  _ < ___) | ||_____| |_) |  __/ | | | (__| | | |
 |_| \\_\\____/___|     |____/ \\___|_| |_|\\___|_| |_|
{RESET}{DIM}  Multi-Turn LLM Benchmark | Trace & Thinking Capture | Prompt Caching{RESET}
{CYAN}======================================================================{RESET}
"""
    print(banner)


def print_turn_summary(trace: TurnTrace) -> None:
    """Print formatted summary of a completed turn."""
    status_icon = colorize("[OK]", GREEN) if trace.parse_success else colorize("[ERR]", RED)
    status_text = (
        f"Int: {colorize(str(trace.parsed_integer), GREEN)}"
        if trace.parse_success
        else colorize(f"Error: {trace.parse_error}", RED)
    )
    thinking_icon = "[THINK] " if trace.thinking_trace else "        "
    latency_str = colorize(f"{trace.latency_ms:.1f}ms", CYAN)

    tokens_str = f"P:{trace.token_usage.prompt_tokens} / C:{trace.token_usage.completion_tokens}"
    if trace.token_usage.cached_tokens:
        tokens_str += f" / Cached:{colorize(str(trace.token_usage.cached_tokens), YELLOW)}"

    print(
        f"  Turn {trace.turn_index:2d} {status_icon} | {status_text:<25} | {thinking_icon}Latency: {latency_str:<12} | Tokens: {tokens_str}"
    )


def print_run_result(result: BenchmarkResult, json_path: Optional[str] = None) -> None:
    """Print overall benchmark result summary."""
    print(f"\n{BOLD}---------------- Benchmark Summary ----------------{RESET}")
    print(f"  Provider:       {colorize(result.provider, CYAN)}")
    print(f"  Model:          {colorize(result.model, CYAN)}")
    print(f"  Turns:          {result.num_turns_completed} / {result.num_turns_requested}")

    all_valid_str = (
        colorize("All turns produced valid integers", GREEN)
        if result.all_valid
        else colorize("Some turns failed integer parsing", RED)
    )
    print(f"  Result:         {all_valid_str}")
    print(f"  Parsed Integers:{colorize(str(result.parsed_integers), GREEN)}")
    print(
        f"  Total Latency:  {result.total_latency_ms:.1f} ms (avg {result.avg_turn_latency_ms:.1f} ms/turn)"
    )
    print(
        f"  Token Usage:    Prompt={result.total_usage.prompt_tokens}, Completion={result.total_usage.completion_tokens}, Total={result.total_usage.total_tokens}"
    )
    if result.total_usage.cached_tokens:
        print(f"  Cache Hits:     {colorize(str(result.total_usage.cached_tokens), YELLOW)} tokens")
    if result.total_usage.reasoning_tokens:
        print(f"  Reasoning:      {colorize(str(result.total_usage.reasoning_tokens), YELLOW)} tokens")
    if json_path:
        print(f"  Saved Trace:    {json_path}")
    print(f"{BOLD}---------------------------------------------------{RESET}\n")


def print_batch_summary(
    batch_result: BatchBenchmarkResult,
    json_path: Optional[str] = None,
    md_path: Optional[str] = None,
) -> None:
    """Print comprehensive summary table of all benchmark runs in a batch."""
    print(f"\n{BOLD}{CYAN}=========================== RSI-Bench Batch Execution Summary ==========================={RESET}")
    print(f"  Batch ID:      {colorize(batch_result.batch_id, CYAN)}")
    print(f"  Timestamp:     {batch_result.timestamp}")
    status_summary = (
        f"{colorize(f'{batch_result.successful_runs} Passed', GREEN)}, "
        f"{colorize(f'{batch_result.failed_runs} Failed', RED) if batch_result.failed_runs else '0 Failed'}"
    )
    print(f"  Completed:     {batch_result.completed_runs} / {batch_result.total_runs} runs ({status_summary})")
    print(f"  Total Latency: {batch_result.total_latency_ms:.1f} ms")
    print(
        f"  Total Tokens:  Prompt={batch_result.total_usage.prompt_tokens}, "
        f"Completion={batch_result.total_usage.completion_tokens}, "
        f"Total={batch_result.total_usage.total_tokens}"
    )
    if batch_result.total_usage.cached_tokens:
        print(f"  Cached Tokens: {colorize(str(batch_result.total_usage.cached_tokens), YELLOW)}")
    if batch_result.total_usage.reasoning_tokens:
        print(f"  Reasoning:     {colorize(str(batch_result.total_usage.reasoning_tokens), YELLOW)}")

    print(f"\n {BOLD}{'#':<3} | {'Status':<7} | {'Run Name':<22} | {'Provider / Model':<30} | {'Integers':<16} | {'Latency':<9} | {'Tokens (P/C/Cached)':<20}{RESET}")
    print(f" {'-'*3}-|-{'-'*7}-|-{'-'*22}-|-{'-'*30}-|-{'-'*16}-|-{'-'*9}-|-{'-'*20}")

    for idx, res in enumerate(batch_result.results, start=1):
        status_txt = "[PASS]" if res.all_valid else "[FAIL]"
        status_color = GREEN if res.all_valid else RED
        status_col = colorize(f"{status_txt:<7}", status_color)
        name = res.config.get("name") or f"{res.provider}_{res.model}"
        if len(name) > 22:
            name = name[:19] + "..."
        prov_model = f"{res.provider}/{res.model}"
        if len(prov_model) > 30:
            prov_model = prov_model[:27] + "..."

        ints_str = str(res.parsed_integers)
        if len(ints_str) > 16:
            ints_str = ints_str[:13] + "..."

        lat_str = f"{res.total_latency_ms:.1f}ms"
        tokens_str = f"{res.total_usage.prompt_tokens}/{res.total_usage.completion_tokens}"
        if res.total_usage.cached_tokens:
            tokens_str += f"/{res.total_usage.cached_tokens}"

        print(f" {idx:<3} | {status_col} | {name:<22} | {prov_model:<30} | {ints_str:<16} | {lat_str:<9} | {tokens_str:<20}")

    if json_path:
        print(f"\n  Batch JSON Report:     {json_path}")
    if md_path:
        print(f"  Batch Markdown Report: {md_path}")
    print(f"{BOLD}{CYAN}========================================================================================={RESET}\n")

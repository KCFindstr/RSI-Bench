"""
CLI formatting and presentation utilities.
Handles Windows console encoding and ANSI colors safely.
"""

from __future__ import annotations

import sys
from typing import Any, List, Optional
from rsi_bench.models import BenchmarkResult, TurnTrace

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

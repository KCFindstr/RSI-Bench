"""
RSI-Bench: Robust Multi-Turn LLM Benchmark Suite.
Supports all major LLM providers, thinking/reasoning trace extraction,
prompt caching, and robust integer output parsing.
"""

__version__ = "0.1.0"

from rsi_bench.models import (
    BatchBenchmarkResult,
    BatchConfig,
    BatchRunItem,
    BenchmarkConfig,
    BenchmarkResult,
    Message,
    TokenUsage,
    TurnTrace,
)
from rsi_bench.parser import ParsedOutput, parse_integer_output
from rsi_bench.runner import BenchmarkRunner, run_batch

__all__ = [
    "BatchBenchmarkResult",
    "BatchConfig",
    "BatchRunItem",
    "BenchmarkConfig",
    "BenchmarkResult",
    "BenchmarkRunner",
    "Message",
    "ParsedOutput",
    "TokenUsage",
    "TurnTrace",
    "parse_integer_output",
    "run_batch",
]

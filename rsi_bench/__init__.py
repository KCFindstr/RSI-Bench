"""
RSI-Bench: Robust Multi-Turn LLM Benchmark Suite.
Supports all major LLM providers, thinking/reasoning trace extraction,
prompt caching, and robust integer output parsing.
"""

__version__ = "0.1.0"

from rsi_bench.models import (
    BenchmarkResult,
    Message,
    TokenUsage,
    TurnTrace,
)
from rsi_bench.parser import ParsedOutput, parse_integer_output
from rsi_bench.runner import BenchmarkRunner

__all__ = [
    "BenchmarkResult",
    "BenchmarkRunner",
    "Message",
    "ParsedOutput",
    "TokenUsage",
    "TurnTrace",
    "parse_integer_output",
]

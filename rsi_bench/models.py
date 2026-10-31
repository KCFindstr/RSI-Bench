"""Data models for RSI-Bench."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Represents a conversational message."""
    role: Literal["user", "assistant", "system"]
    content: str
    thinking: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token usage breakdown, including prompt caching and reasoning tokens."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0

    def add(self, other: TokenUsage) -> TokenUsage:
        """Sum two token usages."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )


class TurnTrace(BaseModel):
    """Execution trace and parsed output for a single benchmark turn."""
    turn_index: int
    prompt: str
    raw_response_text: str
    thinking_trace: Optional[str] = None
    parsed_integer: Optional[int] = None
    parse_success: bool = False
    parse_error: Optional[str] = None
    latency_ms: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_request: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None


class ProviderResponse(BaseModel):
    """Standardized response from any LLM provider."""
    content: str
    thinking: Optional[str] = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_request: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkConfig(BaseModel):
    """Configuration for running a benchmark evaluation."""
    provider: str
    model: str
    num_turns: int = 3
    prompt: str = "Generate a random integer. Do NOT output anything else."
    system_prompt: Optional[str] = None
    enable_thinking: bool = True
    thinking_budget: Optional[int] = 1024
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    seed: Optional[int] = None
    max_tokens: Optional[int] = 2048
    enable_caching: bool = True
    use_local_cache: bool = False
    local_cache_dir: str = ".rsi_cache"
    timeout_seconds: float = 90.0
    max_retries: int = 3
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_headers: Dict[str, str] = Field(default_factory=dict)
    extra_body: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkResult(BaseModel):
    """Comprehensive benchmark execution result with all turn traces."""
    run_id: str
    benchmark_name: str = "RSI-Bench"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provider: str
    model: str
    num_turns_requested: int
    num_turns_completed: int
    parsed_integers: List[Optional[int]] = Field(default_factory=list)
    all_valid: bool = False
    valid_turns_count: int = 0
    total_latency_ms: float = 0.0
    avg_turn_latency_ms: float = 0.0
    total_usage: TokenUsage = Field(default_factory=TokenUsage)
    turns: List[TurnTrace] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

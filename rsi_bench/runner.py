"""
Benchmark runner engine for RSI-Bench.
Orchestrates multi-turn conversation execution, token tracking, caching, thinking capture,
and trace persistence.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, List, Optional
import httpx

from rsi_bench.cache import ResponseCache
from rsi_bench.models import (
    BenchmarkConfig,
    BenchmarkResult,
    Message,
    ProviderResponse,
    TokenUsage,
    TurnTrace,
)
from rsi_bench.parser import parse_integer_output
from rsi_bench.providers import BaseProvider, get_provider
from rsi_bench.storage import StorageManager


class BenchmarkRunner:
    """Orchestrates multi-turn benchmark execution for a single model run."""

    def __init__(
        self,
        config: BenchmarkConfig,
        storage_manager: Optional[StorageManager] = None,
        provider: Optional[BaseProvider] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.config = config
        self.storage = storage_manager or StorageManager()
        self.cache = ResponseCache(
            cache_dir=config.local_cache_dir,
            enabled=config.use_local_cache,
        )
        self.provider = provider or get_provider(
            config.provider,
            config=config,
            http_client=http_client,
        )

    def run(
        self,
        on_turn_start: Optional[Callable[[int, int], None]] = None,
        on_turn_end: Optional[Callable[[TurnTrace], None]] = None,
    ) -> BenchmarkResult:
        """
        Execute the full multi-turn benchmark run.

        Optional hooks:
        - on_turn_start(current_turn, total_turns)
        - on_turn_end(turn_trace)
        """
        run_id = uuid.uuid4().hex[:10]
        messages: List[Message] = []
        turns: List[TurnTrace] = []
        total_usage = TokenUsage()
        total_latency = 0.0
        run_error: Optional[str] = None

        for turn_idx in range(1, self.config.num_turns + 1):
            if on_turn_start:
                on_turn_start(turn_idx, self.config.num_turns)

            prompt_text = self.config.prompt
            user_message = Message(role="user", content=prompt_text)
            messages.append(user_message)

            # Check cache if enabled
            cache_key = self.cache.compute_cache_key(
                provider=self.config.provider,
                model=self.config.model,
                messages=[m.model_dump() for m in messages],
                system_prompt=self.config.system_prompt,
                extra_params={
                    "thinking": self.config.enable_thinking,
                    "budget": self.config.thinking_budget,
                    "temp": self.config.temperature,
                },
            )

            cached_resp = self.cache.get(cache_key)
            start_time = time.perf_counter()

            try:
                if cached_resp:
                    response = cached_resp
                    latency_ms = 0.0
                else:
                    response = self.provider.send_turn(
                        messages=messages,
                        system_prompt=self.config.system_prompt,
                    )
                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    self.cache.set(cache_key, response)

                total_latency += latency_ms
                total_usage = total_usage.add(response.usage)

                # Parse output integer and extract thinking trace
                parsed = parse_integer_output(
                    raw_text=response.content,
                    existing_thinking=response.thinking,
                )

                thinking_trace = parsed.extracted_thinking or response.thinking

                trace = TurnTrace(
                    turn_index=turn_idx,
                    prompt=prompt_text,
                    raw_response_text=response.content,
                    thinking_trace=thinking_trace,
                    parsed_integer=parsed.integer,
                    parse_success=parsed.success,
                    parse_error=parsed.error_message,
                    latency_ms=latency_ms,
                    token_usage=response.usage,
                    provider_metadata=response.metadata,
                    raw_request=response.raw_request,
                    raw_response=response.raw_response,
                )
                turns.append(trace)

                if on_turn_end:
                    on_turn_end(trace)

                # Append assistant reply to conversation history for next turns
                messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        thinking=thinking_trace,
                        metadata=response.metadata,
                    )
                )

            except Exception as e:
                run_error = str(e)
                # Record error on current turn and abort further turns
                trace = TurnTrace(
                    turn_index=turn_idx,
                    prompt=prompt_text,
                    raw_response_text="",
                    parse_success=False,
                    parse_error=f"Provider execution failed: {e}",
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                )
                turns.append(trace)
                if on_turn_end:
                    on_turn_end(trace)
                break

        # Compute summary statistics
        parsed_integers = [t.parsed_integer for t in turns if t.parsed_integer is not None]
        valid_turns_count = sum(1 for t in turns if t.parse_success)
        all_valid = (valid_turns_count == self.config.num_turns) and (run_error is None)
        completed_turns = len(turns)
        avg_latency = (total_latency / completed_turns) if completed_turns > 0 else 0.0

        result = BenchmarkResult(
            run_id=run_id,
            benchmark_name="RSI-Bench",
            provider=self.config.provider,
            model=self.config.model,
            num_turns_requested=self.config.num_turns,
            num_turns_completed=completed_turns,
            parsed_integers=parsed_integers,
            all_valid=all_valid,
            valid_turns_count=valid_turns_count,
            total_latency_ms=total_latency,
            avg_turn_latency_ms=avg_latency,
            total_usage=total_usage,
            turns=turns,
            config=self.config.model_dump(),
            error=run_error,
        )

        # Save result to traces and summary files
        self.storage.save_result(result)

        return result

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
from rsi_bench.config import build_benchmark_configs
from rsi_bench.models import (
    BatchBenchmarkResult,
    BatchConfig,
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

    def close(self) -> None:
        """Close provider resources and underlying HTTP client."""
        if hasattr(self, "provider") and self.provider:
            self.provider.close()

    def __enter__(self) -> BenchmarkRunner:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

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


def run_batch(
    batch_config: BatchConfig,
    output_dir: Optional[str] = None,
    mock_override: bool = False,
    filter_name: Optional[str] = None,
    turns_override: Optional[int] = None,
    api_key_override: Optional[str] = None,
    base_url_override: Optional[str] = None,
    cli_overrides: Optional[dict[str, Any]] = None,
    storage_manager: Optional[StorageManager] = None,
    http_client: Optional[httpx.Client] = None,
    on_run_start: Optional[Callable[[int, int, str, BenchmarkConfig], None]] = None,
    on_run_end: Optional[Callable[[int, int, BenchmarkResult], None]] = None,
    on_turn_start: Optional[Callable[[int, int], None]] = None,
    on_turn_end: Optional[Callable[[TurnTrace], None]] = None,
) -> BatchBenchmarkResult:
    """
    Execute a batch of benchmarks specified by BatchConfig.
    Saves individual run traces, appends to CSV log, and generates an aggregate batch report.
    """
    batch_id = uuid.uuid4().hex[:10]
    effective_output_dir = output_dir or batch_config.output_dir or "results"
    storage = storage_manager or StorageManager(output_dir=effective_output_dir)

    merged_overrides: dict[str, Any] = dict(cli_overrides or {})
    if mock_override:
        merged_overrides["mock"] = True
    if filter_name is not None:
        merged_overrides["filter"] = filter_name
    if turns_override is not None:
        merged_overrides["turns"] = turns_override
    if api_key_override is not None:
        merged_overrides["api_key"] = api_key_override
    if base_url_override is not None:
        merged_overrides["base_url"] = base_url_override

    run_configs = build_benchmark_configs(batch_config, cli_overrides=merged_overrides)
    total_runs = len(run_configs)

    results: List[BenchmarkResult] = []
    total_usage = TokenUsage()
    total_latency_ms = 0.0

    for idx, (run_name, config) in enumerate(run_configs, start=1):
        if on_run_start:
            on_run_start(idx, total_runs, run_name, config)

        runner: Optional[BenchmarkRunner] = None
        try:
            runner = BenchmarkRunner(
                config=config,
                storage_manager=storage,
                http_client=http_client,
            )
            res = runner.run(on_turn_start=on_turn_start, on_turn_end=on_turn_end)
        except Exception as e:
            res = BenchmarkResult(
                run_id=uuid.uuid4().hex[:10],
                provider=config.provider,
                model=config.model,
                num_turns_requested=config.num_turns,
                num_turns_completed=0,
                all_valid=False,
                config=config.model_dump(),
                error=f"Run initialization error: {e}",
            )
            storage.save_result(res)
        finally:
            if runner:
                runner.close()

        results.append(res)
        total_latency_ms += res.total_latency_ms
        total_usage = total_usage.add(res.total_usage)

        if on_run_end:
            on_run_end(idx, total_runs, res)

    successful_runs = sum(1 for r in results if r.all_valid)
    failed_runs = len(results) - successful_runs
    all_successful = (successful_runs == total_runs) and (total_runs > 0)

    batch_result = BatchBenchmarkResult(
        batch_id=batch_id,
        total_runs=total_runs,
        completed_runs=len(results),
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        all_successful=all_successful,
        total_latency_ms=total_latency_ms,
        total_usage=total_usage,
        results=results,
    )

    storage.save_batch_result(batch_result)
    return batch_result

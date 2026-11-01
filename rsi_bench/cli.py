"""
Command line interface for RSI-Bench.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from rsi_bench.cache import ResponseCache
from rsi_bench.config import (
    PROVIDER_REGISTRY,
    find_default_config_path,
    get_api_key_for_provider,
    get_available_configured_providers,
    load_batch_config,
)
from rsi_bench.models import BenchmarkConfig
from rsi_bench.runner import BenchmarkRunner, run_batch
from rsi_bench.storage import StorageManager
from rsi_bench.utils.formatting import (
    BOLD,
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    colorize,
    print_banner,
    print_batch_summary,
    print_run_result,
    print_turn_summary,
)


def list_providers() -> None:
    """Print an informative table of all supported providers and their key status."""
    print(f"\n{BOLD}Supported Providers in RSI-Bench:{RESET}\n")
    print(f" {'Provider':<18} | {'Env Var':<24} | {'Status':<12} | {'Default Model':<28}")
    print(f" {'-'*18}-|-{'-'*24}-|-{'-'*12}-|-{'-'*28}")

    for name, meta in sorted(PROVIDER_REGISTRY.items()):
        key_found = get_api_key_for_provider(name) is not None
        status = colorize("Configured", GREEN) if key_found else colorize("Missing Key", RED)
        if name == "generic_openai":
            status = colorize("Optional Key", YELLOW)

        env_str = ", ".join(meta.env_key_names)
        print(f" {name:<18} | {env_str:<24} | {status:<21} | {meta.default_model:<28}")

    print(f"\n  Run with {colorize('--mock', CYAN)} to run benchmark without an API key.")
    print(f"  Run with {colorize('--all-configured', CYAN)} to benchmark all configured providers.\n")


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for RSI-Bench CLI."""
    parser = argparse.ArgumentParser(
        description="RSI-Bench: Multi-turn LLM benchmark measuring integer generation, prompt caching, and thinking traces.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-p", "--provider",
        type=str,
        default=None,
        help="Provider to benchmark (e.g. gemini_interactions, anthropic, openai_responses, openai_chat, openai_completion, deepseek, openrouter, gemini, groq, mistral, together, cohere, generic, mock). Defaults to openai_chat or batch config.",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help="Model identifier (defaults to provider's default model)",
    )
    parser.add_argument(
        "-n", "--turns",
        type=int,
        default=None,
        help="Number of conversation turns (defaults to 3 or config value)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="The prompt sent in each conversation turn (defaults to 'Generate a random integer. Do NOT output anything else.' or config value)",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="Optional system prompt",
    )
    parser.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable model thinking/reasoning extraction and configuration",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Token budget for thinking (Anthropic / Gemini, defaults to 1024 or config value)",
    )
    parser.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable provider prompt caching flags/headers",
    )
    parser.add_argument(
        "--use-local-cache",
        action="store_true",
        help="Cache provider responses locally on disk to avoid re-calls",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the local response cache and exit",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Explicit API key (overrides environment variable)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Custom API base URL",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (defaults to 1.0 or config value)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max completion tokens (defaults to 2048 or config value)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save traces and summaries (defaults to results or config value)",
    )
    parser.add_argument(
        "-c", "--config",
        nargs="?",
        const="AUTO",
        type=str,
        default=None,
        help="Path to JSON or YAML config file defining multiple benchmark runs. If specified without a path, searches for config.yaml/json.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch benchmark from default config file (e.g. config.yaml or config.json)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter batch benchmark runs by name or provider substring",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Shortcut to run with offline MockProvider (or force mock mode in batch)",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all supported providers and their API key configuration status",
    )
    parser.add_argument(
        "--all-configured",
        action="store_true",
        help="Run benchmark against all providers with detected API keys",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Generate Artificial Analysis bar chart and multi-turn trajectory line graph after benchmark execution",
    )

    return parser


def run_single_benchmark(config: BenchmarkConfig, output_dir: str) -> bool:
    """Execute a single benchmark run."""
    print(f"\n[*] Running RSI-Bench: Provider={colorize(config.provider, CYAN)}, Model={colorize(config.model, CYAN)}, Turns={config.num_turns}")

    from rsi_bench.storage import sanitize_filename_component
    storage = StorageManager(output_dir=output_dir)
    runner = None
    try:
        runner = BenchmarkRunner(config=config, storage_manager=storage)
    except Exception as e:
        print(colorize(f"Initialization Error: {e}", RED))
        return False

    def on_turn_start(current: int, total: int) -> None:
        pass

    def on_turn_end(trace) -> None:
        print_turn_summary(trace)

    try:
        result = runner.run(on_turn_start=on_turn_start, on_turn_end=on_turn_end)
    finally:
        if runner:
            runner.close()

    safe_prov = sanitize_filename_component(result.provider)
    safe_model = sanitize_filename_component(result.model)
    saved_path = storage.traces_dir / f"{safe_prov}_{safe_model}_{result.run_id}.json"
    print_run_result(result, json_path=str(saved_path))
    return result.all_valid


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.clear_cache:
        cache = ResponseCache()
        count = cache.clear()
        print(f"Cleared {count} cached response entries.")
        return 0

    if parsed_args.list_providers:
        print_banner()
        list_providers()
        return 0

    print_banner()

    # Check if batch mode is triggered
    is_batch_mode = False
    config_path: Optional[Path] = None

    if parsed_args.config:
        if parsed_args.config == "AUTO":
            config_path = find_default_config_path()
            if not config_path:
                print(colorize("Error: No default config file found (e.g. config.yaml, config.json). Provide path via -c <path>.", RED))
                return 1
        else:
            config_path = Path(parsed_args.config)
        is_batch_mode = True
    elif parsed_args.batch or parsed_args.filter is not None:
        config_path = find_default_config_path()
        if not config_path:
            trigger = "--filter" if parsed_args.filter else "--batch"
            print(colorize(f"Error: No default config file found for {trigger} (e.g. config.yaml, config.json). Provide path via -c <path>.", RED))
            return 1
        is_batch_mode = True
    elif parsed_args.provider is None and not parsed_args.mock and not parsed_args.all_configured:
        # User didn't specify provider or mock; check if a default config file exists
        default_cfg = find_default_config_path()
        if default_cfg:
            config_path = default_cfg
            is_batch_mode = True

    if is_batch_mode and config_path:
        print(f"Loading batch configuration from: {colorize(str(config_path), CYAN)}")
        try:
            batch_config = load_batch_config(config_path)
        except Exception as e:
            print(colorize(f"Configuration Error: {e}", RED))
            return 1

        effective_output_dir = parsed_args.output_dir or batch_config.output_dir or "results"
        storage = StorageManager(output_dir=effective_output_dir)

        cli_overrides: dict[str, Any] = {
            "mock": parsed_args.mock,
            "filter": parsed_args.filter,
            "turns": parsed_args.turns,
            "api_key": parsed_args.api_key,
            "base_url": parsed_args.base_url,
            "prompt": parsed_args.prompt,
            "system_prompt": parsed_args.system_prompt,
            "thinking": parsed_args.thinking,
            "thinking_budget": parsed_args.thinking_budget,
            "cache": parsed_args.cache,
            "use_local_cache": True if parsed_args.use_local_cache else None,
            "temperature": parsed_args.temperature,
            "max_tokens": parsed_args.max_tokens,
        }
        cli_overrides = {k: v for k, v in cli_overrides.items() if v is not None}

        def on_run_start(idx: int, total: int, run_name: str, cfg: BenchmarkConfig) -> None:
            print(f"\n{BOLD}[{idx}/{total}] Benchmark: {colorize(run_name, CYAN)} (Provider={cfg.provider}, Model={cfg.model}, Turns={cfg.num_turns}){RESET}")

        def on_turn_end(trace) -> None:
            print_turn_summary(trace)

        batch_result = run_batch(
            batch_config=batch_config,
            output_dir=effective_output_dir,
            mock_override=parsed_args.mock,
            filter_name=parsed_args.filter,
            turns_override=parsed_args.turns,
            api_key_override=parsed_args.api_key,
            base_url_override=parsed_args.base_url,
            cli_overrides=cli_overrides,
            storage_manager=storage,
            on_run_start=on_run_start,
            on_turn_end=on_turn_end,
        )

        batch_json_path = storage.output_dir / f"batch_{batch_result.batch_id}.json"
        batch_md_path = storage.output_dir / f"batch_{batch_result.batch_id}.md"

        print_batch_summary(
            batch_result,
            json_path=str(batch_json_path),
            md_path=str(batch_md_path),
        )

        if parsed_args.charts and batch_result.total_runs > 0:
            from rsi_bench.visualization import generate_all_charts
            charts_out = storage.output_dir / "charts"
            chart_artifacts = generate_all_charts(
                data_source=batch_json_path,
                output_dir=charts_out,
                num_turns=parsed_args.turns or 5,
            )
            print(colorize(f"\n[+] Generated Benchmark Visualizations in: {charts_out}", GREEN))
            for k, p in chart_artifacts.items():
                print(f"    - {k:<18}: file:///{p.absolute().as_posix()}")

        if batch_result.total_runs == 0:
            print(colorize("Warning: No benchmark runs matched the specified filter or criteria.", YELLOW))
            return 1

        return 0 if batch_result.all_successful else 1

    turns_count = parsed_args.turns if parsed_args.turns is not None else 3
    single_output_dir = parsed_args.output_dir or "results"
    prompt_str = parsed_args.prompt or "Generate a random integer. Do NOT output anything else."
    thinking_flag = parsed_args.thinking if parsed_args.thinking is not None else True
    thinking_budget = parsed_args.thinking_budget if parsed_args.thinking_budget is not None else 1024
    caching_flag = parsed_args.cache if parsed_args.cache is not None else True
    temp_val = parsed_args.temperature if parsed_args.temperature is not None else 1.0
    max_toks = parsed_args.max_tokens if parsed_args.max_tokens is not None else 2048

    if parsed_args.all_configured:
        configured = get_available_configured_providers()
        if not configured:
            print(colorize("No provider API keys detected in environment. Try running with --mock.", YELLOW))
            return 1

        print(f"Found {len(configured)} configured provider(s): {', '.join(configured)}")
        overall_success = True
        for provider_name in configured:
            meta = PROVIDER_REGISTRY[provider_name]
            config = BenchmarkConfig(
                provider=provider_name,
                model=meta.default_model,
                num_turns=turns_count,
                prompt=prompt_str,
                system_prompt=parsed_args.system_prompt,
                enable_thinking=thinking_flag,
                thinking_budget=thinking_budget,
                temperature=temp_val,
                max_tokens=max_toks,
                enable_caching=caching_flag,
                use_local_cache=parsed_args.use_local_cache,
            )
            success = run_single_benchmark(config, single_output_dir)
            if not success:
                overall_success = False

        return 0 if overall_success else 1

    # Single provider execution
    provider_name = "mock" if parsed_args.mock else (parsed_args.provider or "openai_chat")
    model_name = parsed_args.model
    if not model_name:
        meta = PROVIDER_REGISTRY.get(provider_name.lower())
        model_name = meta.default_model if meta else "default"

    config = BenchmarkConfig(
        provider=provider_name,
        model=model_name,
        num_turns=turns_count,
        prompt=prompt_str,
        system_prompt=parsed_args.system_prompt,
        enable_thinking=thinking_flag,
        thinking_budget=thinking_budget,
        temperature=temp_val,
        max_tokens=max_toks,
        enable_caching=caching_flag,
        use_local_cache=parsed_args.use_local_cache,
        api_key=parsed_args.api_key,
        base_url=parsed_args.base_url,
    )

    success = run_single_benchmark(config, single_output_dir)
    if success and parsed_args.charts:
        from rsi_bench.visualization import generate_all_charts
        charts_out = Path(single_output_dir) / "charts"
        chart_artifacts = generate_all_charts(
            data_source=Path(single_output_dir) / "benchmark_summary.csv",
            output_dir=charts_out,
            num_turns=parsed_args.turns or 5,
        )
        print(colorize(f"\n[+] Generated Benchmark Visualizations in: {charts_out}", GREEN))
        for k, p in chart_artifacts.items():
            print(f"    - {k:<18}: file:///{p.absolute().as_posix()}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

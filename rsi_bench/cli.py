"""
Command line interface for RSI-Bench.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from rsi_bench.cache import ResponseCache
from rsi_bench.config import (
    PROVIDER_REGISTRY,
    get_api_key_for_provider,
    get_available_configured_providers,
)
from rsi_bench.models import BenchmarkConfig
from rsi_bench.runner import BenchmarkRunner
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
        default="openai_chat",
        help="Provider to benchmark (e.g. gemini_interactions, anthropic, openai_responses, openai_chat, openai_completion, deepseek, openrouter, gemini, groq, mistral, together, cohere, generic, mock)",
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
        default=3,
        help="Number of conversation turns",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Generate a random integer. Do NOT output anything else.",
        help="The prompt sent in each conversation turn",
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
        default=True,
        help="Enable model thinking/reasoning extraction and configuration",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=1024,
        help="Token budget for thinking (Anthropic / Gemini)",
    )
    parser.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=True,
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
        default=1.0,
        help="Sampling temperature",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Max completion tokens",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory to save traces and summaries",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Shortcut to run with offline MockProvider",
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

    return parser


def run_single_benchmark(config: BenchmarkConfig, output_dir: str) -> bool:
    """Execute a single benchmark run."""
    print(f"\n[*] Running RSI-Bench: Provider={colorize(config.provider, CYAN)}, Model={colorize(config.model, CYAN)}, Turns={config.num_turns}")

    storage = StorageManager(output_dir=output_dir)
    try:
        runner = BenchmarkRunner(config=config, storage_manager=storage)
    except Exception as e:
        print(colorize(f"Initialization Error: {e}", RED))
        return False

    def on_turn_start(current: int, total: int) -> None:
        pass

    def on_turn_end(trace) -> None:
        print_turn_summary(trace)

    result = runner.run(on_turn_start=on_turn_start, on_turn_end=on_turn_end)
    saved_path = storage.traces_dir / f"{result.provider}_{result.model.replace('/', '_')}_{result.run_id}.json"
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
                num_turns=parsed_args.turns,
                prompt=parsed_args.prompt,
                system_prompt=parsed_args.system_prompt,
                enable_thinking=parsed_args.thinking,
                thinking_budget=parsed_args.thinking_budget,
                temperature=parsed_args.temperature,
                max_tokens=parsed_args.max_tokens,
                enable_caching=parsed_args.cache,
                use_local_cache=parsed_args.use_local_cache,
            )
            success = run_single_benchmark(config, parsed_args.output_dir)
            if not success:
                overall_success = False

        return 0 if overall_success else 1

    # Single provider execution
    provider_name = "mock" if parsed_args.mock else parsed_args.provider
    model_name = parsed_args.model
    if not model_name:
        meta = PROVIDER_REGISTRY.get(provider_name.lower())
        model_name = meta.default_model if meta else "default"

    config = BenchmarkConfig(
        provider=provider_name,
        model=model_name,
        num_turns=parsed_args.turns,
        prompt=parsed_args.prompt,
        system_prompt=parsed_args.system_prompt,
        enable_thinking=parsed_args.thinking,
        thinking_budget=parsed_args.thinking_budget,
        temperature=parsed_args.temperature,
        max_tokens=parsed_args.max_tokens,
        enable_caching=parsed_args.cache,
        use_local_cache=parsed_args.use_local_cache,
        api_key=parsed_args.api_key,
        base_url=parsed_args.base_url,
    )

    success = run_single_benchmark(config, parsed_args.output_dir)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

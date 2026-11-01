"""
Configuration and provider defaults for RSI-Bench.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from rsi_bench.models import BatchConfig, BatchRunItem, BenchmarkConfig


@dataclass
class ProviderMetadata:
    """Metadata and defaults for an LLM provider."""
    name: str
    display_name: str
    default_model: str
    default_base_url: str
    env_key_names: List[str]
    supports_thinking: bool = True
    supports_prompt_caching: bool = True
    doc_url: str = ""


PROVIDER_REGISTRY: Dict[str, ProviderMetadata] = {
    "anthropic": ProviderMetadata(
        name="anthropic",
        display_name="Anthropic (Messages API)",
        default_model="claude-3-7-sonnet-20250219",
        default_base_url="https://api.anthropic.com/v1",
        env_key_names=["ANTHROPIC_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://docs.anthropic.com/en/api/messages",
    ),
    "gemini_interactions": ProviderMetadata(
        name="gemini_interactions",
        display_name="Google Gemini (Interactions API)",
        default_model="gemini-2.5-flash",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        env_key_names=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://ai.google.dev/api/rest",
    ),
    "gemini": ProviderMetadata(
        name="gemini",
        display_name="Google Gemini (Content API - generateContent)",
        default_model="gemini-2.5-flash",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        env_key_names=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://ai.google.dev/api/rest",
    ),
    "openai_chat": ProviderMetadata(
        name="openai_chat",
        display_name="OpenAI (Chat Completions Route)",
        default_model="gpt-4o",
        default_base_url="https://api.openai.com/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://platform.openai.com/docs/api-reference/chat",
    ),
    "openai_responses": ProviderMetadata(
        name="openai_responses",
        display_name="OpenAI (Responses API)",
        default_model="gpt-4o",
        default_base_url="https://api.openai.com/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://platform.openai.com/docs/api-reference/responses",
    ),
    "openai_completion": ProviderMetadata(
        name="openai_completion",
        display_name="OpenAI (Text Completions Route)",
        default_model="gpt-3.5-turbo-instruct",
        default_base_url="https://api.openai.com/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=False,
        supports_prompt_caching=True,
        doc_url="https://platform.openai.com/docs/api-reference/completions",
    ),
    "deepseek": ProviderMetadata(
        name="deepseek",
        display_name="DeepSeek",
        default_model="deepseek-reasoner",
        default_base_url="https://api.deepseek.com",
        env_key_names=["DEEPSEEK_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://api-docs.deepseek.com/",
    ),
    "openrouter": ProviderMetadata(
        name="openrouter",
        display_name="OpenRouter",
        default_model="deepseek/deepseek-r1",
        default_base_url="https://openrouter.ai/api/v1",
        env_key_names=["OPENROUTER_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://openrouter.ai/docs",
    ),
    "groq": ProviderMetadata(
        name="groq",
        display_name="Groq",
        default_model="deepseek-r1-distill-llama-70b",
        default_base_url="https://api.groq.com/openai/v1",
        env_key_names=["GROQ_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="https://console.groq.com/docs",
    ),
    "mistral": ProviderMetadata(
        name="mistral",
        display_name="Mistral AI",
        default_model="mistral-large-latest",
        default_base_url="https://api.mistral.ai/v1",
        env_key_names=["MISTRAL_API_KEY"],
        supports_thinking=False,
        supports_prompt_caching=False,
        doc_url="https://docs.mistral.ai/",
    ),
    "together": ProviderMetadata(
        name="together",
        display_name="Together AI",
        default_model="deepseek-ai/DeepSeek-R1",
        default_base_url="https://api.together.xyz/v1",
        env_key_names=["TOGETHER_API_KEY", "TOGETHERAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="https://docs.together.ai/",
    ),
    "cohere": ProviderMetadata(
        name="cohere",
        display_name="Cohere (V2 Chat)",
        default_model="command-r-plus-08-2024",
        default_base_url="https://api.cohere.com/v2",
        env_key_names=["COHERE_API_KEY", "CO_API_KEY"],
        supports_thinking=False,
        supports_prompt_caching=False,
        doc_url="https://docs.cohere.com/reference/chat",
    ),
    "generic_openai": ProviderMetadata(
        name="generic_openai",
        display_name="Generic OpenAI-Compatible (Ollama, vLLM, LMStudio, etc.)",
        default_model="default",
        default_base_url="http://localhost:11434/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="",
    ),
}

CANONICAL_PROVIDER_MAP: Dict[str, str] = {
    "claude": "anthropic",
    "google": "gemini",
    "gemini_content": "gemini",
    "gemini-interactions": "gemini_interactions",
    "interactions": "gemini_interactions",
    "openai": "openai_chat",
    "openai_text": "openai_completion",
    "completion": "openai_completion",
    "generic": "generic_openai",
    "ollama": "generic_openai",
    "togetherai": "together",
}

PROVIDER_KEY_FAMILY_MAP: Dict[str, List[str]] = {
    "anthropic": ["anthropic", "claude"],
    "claude": ["claude", "anthropic"],
    "gemini": ["gemini", "google", "gemini_content"],
    "gemini_content": ["gemini_content", "gemini", "google"],
    "google": ["google", "gemini", "gemini_content"],
    "gemini_interactions": ["gemini_interactions", "gemini-interactions", "interactions", "gemini", "google"],
    "gemini-interactions": ["gemini-interactions", "gemini_interactions", "interactions", "gemini", "google"],
    "interactions": ["interactions", "gemini_interactions", "gemini-interactions", "gemini", "google"],
    "openai": ["openai", "openai_chat", "openai_responses", "openai_completion"],
    "openai_chat": ["openai_chat", "openai"],
    "openai_responses": ["openai_responses", "openai"],
    "openai_completion": ["openai_completion", "openai", "openai_chat", "openai_text", "completion"],
    "openai_text": ["openai_text", "openai_completion", "openai"],
    "completion": ["completion", "openai_completion", "openai"],
    "deepseek": ["deepseek"],
    "openrouter": ["openrouter"],
    "groq": ["groq"],
    "mistral": ["mistral"],
    "together": ["together", "togetherai"],
    "togetherai": ["togetherai", "together"],
    "cohere": ["cohere"],
    "generic": ["generic", "generic_openai", "ollama", "openai"],
    "generic_openai": ["generic_openai", "generic", "ollama", "openai"],
    "ollama": ["ollama", "generic_openai", "generic"],
}


def get_provider_key_candidates(provider_name: str) -> List[str]:
    """Return ordered list of candidate key names to check for a provider."""
    p_lower = provider_name.strip().lower()
    canonical = CANONICAL_PROVIDER_MAP.get(p_lower, p_lower)
    candidates: List[str] = [provider_name.strip(), p_lower]
    if canonical not in candidates:
        candidates.append(canonical)
    for k in [p_lower, canonical]:
        for family_key in PROVIDER_KEY_FAMILY_MAP.get(k, []):
            if family_key not in candidates:
                candidates.append(family_key)
    return candidates


def get_api_key_for_provider(provider_name: str, explicit_key: Optional[str] = None) -> Optional[str]:
    """Retrieve the API key for a provider from explicit argument, registry, or environment variables."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    p_lower = provider_name.strip().lower()
    canonical = CANONICAL_PROVIDER_MAP.get(p_lower, p_lower)
    meta = PROVIDER_REGISTRY.get(p_lower) or PROVIDER_REGISTRY.get(canonical)

    if meta:
        for env_name in meta.env_key_names:
            key = os.environ.get(env_name)
            if key and key.strip():
                return key.strip()

    # Direct uppercase variable name fallback (e.g. MOCK_API_KEY)
    direct_env = os.environ.get(f"{provider_name.upper()}_API_KEY")
    if direct_env and direct_env.strip():
        return direct_env.strip()

    canonical_env = os.environ.get(f"{canonical.upper()}_API_KEY")
    if canonical_env and canonical_env.strip():
        return canonical_env.strip()

    return None


def get_available_configured_providers() -> List[str]:
    """Return list of provider names that currently have API keys set in the environment."""
    configured: List[str] = []
    for name, meta in PROVIDER_REGISTRY.items():
        if name == "generic_openai":
            continue  # local generic doesn't necessarily need a real key
        for env_name in meta.env_key_names:
            if os.environ.get(env_name):
                configured.append(name)
                break
    return configured


DEFAULT_CONFIG_FILENAMES = [
    "config.local.yaml",
    "config.local.yml",
    "config.local.json",
    "config.yaml",
    "config.yml",
    "config.json",
    "benchmark_config.local.yaml",
    "benchmark_config.local.yml",
    "benchmark_config.local.json",
    "benchmark_config.yaml",
    "benchmark_config.yml",
    "benchmark_config.json",
]

FIELD_ALIASES: Dict[str, str] = {
    "turns": "num_turns",
    "thinking": "enable_thinking",
    "thinking_level": "thinking_level",
    "reasoning_effort": "thinking_level",
    "reasoning_level": "thinking_level",
    "effort": "thinking_level",
    "level": "thinking_level",
    "cache": "enable_caching",
    "local_cache": "use_local_cache",
    "cache_dir": "local_cache_dir",
    "key": "api_key",
    "url": "base_url",
    "headers": "extra_headers",
    "body": "extra_body",
}


def _normalize_dict_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize user-friendly field alias keys to model field names."""
    normalized: Dict[str, Any] = {}
    for k, v in d.items():
        mapped_key = FIELD_ALIASES.get(k, k)
        normalized[mapped_key] = v
    return normalized


def _expand_env_vars(obj: Any) -> Any:
    """Recursively expand environment variables (${VAR}, ${VAR:-default}, $VAR, env:VAR, env(VAR))."""
    if isinstance(obj, str):
        trimmed = obj.strip()
        if trimmed.startswith("env:"):
            target = trimmed[4:].strip()
            if ":-" in target:
                var_name, default_val = target.split(":-", 1)
                return os.environ.get(var_name.strip()) or default_val
            return os.environ.get(target, "")
        if trimmed.startswith("env(") and trimmed.endswith(")"):
            target = trimmed[4:-1].strip()
            if ":-" in target:
                var_name, default_val = target.split(":-", 1)
                return os.environ.get(var_name.strip()) or default_val
            return os.environ.get(target, "")

        escaped_marker = "__DOUBLED_DOLLAR_MARKER__"
        text = obj.replace("$$", escaped_marker)

        def _replace_match(m: re.Match) -> str:
            braced = m.group(1)
            if braced is not None:
                if ":-" in braced:
                    var_name, default_val = braced.split(":-", 1)
                    return os.environ.get(var_name.strip()) or default_val
                elif ":" in braced:
                    var_name, default_val = braced.split(":", 1)
                    return os.environ.get(var_name.strip()) or default_val
                return os.environ.get(braced.strip(), "")

            bare = m.group(2)
            if bare is not None:
                return os.environ.get(bare, "")

            return m.group(0)

        # Match ${VAR} or ${VAR:-default} or $VAR (where VAR starts with a letter/underscore).
        # Does NOT match bare numbers like $100.
        pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*(?:(?::-|:)[^}]*)?)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
        expanded = re.sub(pattern, _replace_match, text)
        return expanded.replace(escaped_marker, "$")
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(elem) for elem in obj]
    return obj


def parse_batch_config_data(raw_data: Any) -> BatchConfig:
    """Validate and construct a BatchConfig from a parsed dictionary or list."""
    if raw_data is None:
        raw_data = {}

    if isinstance(raw_data, list):
        data: Dict[str, Any] = {"runs": raw_data}
    elif isinstance(raw_data, dict):
        data = dict(raw_data)
    else:
        raise ValueError(f"Invalid configuration root type: {type(raw_data).__name__}")

    if "benchmarks" in data and "runs" not in data:
        data["runs"] = data.pop("benchmarks")
    elif "runs" not in data and "provider" in data:
        data["runs"] = [data]

    if "defaults" in data and isinstance(data["defaults"], dict):
        data["defaults"] = _normalize_dict_keys(data["defaults"])

    normalized_runs = []
    for item in data.get("runs", []):
        if isinstance(item, dict):
            norm = _normalize_dict_keys(item)
            if "tags" in norm and isinstance(norm["tags"], str):
                norm["tags"] = [t.strip() for t in norm["tags"].split(",") if t.strip()]
            normalized_runs.append(norm)
        else:
            normalized_runs.append(item)
    data["runs"] = normalized_runs

    return BatchConfig(**data)


def load_batch_config(config_path: Union[str, Path]) -> BatchConfig:
    """
    Load a batch benchmark configuration file.
    Supports YAML (.yaml, .yml), JSON (.json), and TOML (.toml).
    """
    path = Path(config_path)
    if not path.is_file():
        # Fallback: check relative to project root or filename inside project root
        project_root = Path(__file__).resolve().parent.parent
        if (project_root / path).is_file():
            path = project_root / path
        elif (project_root / path.name).is_file():
            path = project_root / path.name
        else:
            raise FileNotFoundError(f"Configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    raw_data: Any = None
    if suffix in [".yaml", ".yml"]:
        try:
            import yaml
            raw_data = yaml.safe_load(content)
        except ImportError:
            raise ImportError(
                f"PyYAML is required to parse YAML config files ({path}). "
                "Install it with 'pip install pyyaml' or use JSON format."
            )
    elif suffix == ".json":
        raw_data = json.loads(content)
    elif suffix == ".toml":
        try:
            import tomllib
            raw_data = tomllib.loads(content)
        except ImportError:
            raise ImportError("tomllib is required to parse TOML configuration files.")
    else:
        # Auto-detect format: try JSON, then YAML
        try:
            raw_data = json.loads(content)
        except Exception:
            try:
                import yaml
                raw_data = yaml.safe_load(content)
            except Exception:
                raise ValueError(
                    f"Could not parse configuration file '{path}'. Supported formats: YAML, JSON, TOML."
                )

    if raw_data is None:
        raw_data = {}

    if not isinstance(raw_data, (dict, list)):
        raise ValueError(f"Invalid configuration in {path}: expected dict or list, got {type(raw_data).__name__}")

    raw_data = _expand_env_vars(raw_data)
    return parse_batch_config_data(raw_data)


def find_default_config_path(search_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find the first matching default configuration file in search_dir, current directory, or project root."""
    if search_dir:
        base = Path(search_dir)
        for name in DEFAULT_CONFIG_FILENAMES:
            candidate = base / name
            if candidate.is_file():
                return candidate
        return None

    # Check current working directory first
    cwd = Path.cwd()
    for name in DEFAULT_CONFIG_FILENAMES:
        candidate = cwd / name
        if candidate.is_file():
            return candidate

    # Check project root directory where rsi_bench resides
    project_root = Path(__file__).resolve().parent.parent
    if project_root != cwd:
        for name in DEFAULT_CONFIG_FILENAMES:
            candidate = project_root / name
            if candidate.is_file():
                return candidate

    return None


def build_benchmark_configs(
    batch_config: BatchConfig,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, BenchmarkConfig]]:
    """
    Transform BatchConfig into executable (run_name, BenchmarkConfig) instances.
    Applies defaults, resolves API keys/base URLs in precedence order,
    and incorporates CLI overrides.
    """
    overrides = cli_overrides or {}
    defaults = batch_config.defaults or {}
    configs: List[Tuple[str, BenchmarkConfig]] = []

    filter_str = overrides.get("filter")
    if filter_str:
        filter_str = filter_str.strip().lower()

    for idx, run_item in enumerate(batch_config.runs, start=1):
        if not run_item.enabled:
            continue

        raw_provider = run_item.provider.strip()
        provider = "mock" if overrides.get("mock") else raw_provider

        # Resolve model
        if run_item.model and run_item.model.strip():
            model = run_item.model.strip()
        else:
            canon = CANONICAL_PROVIDER_MAP.get(raw_provider.lower(), raw_provider.lower())
            meta = (
                PROVIDER_REGISTRY.get(raw_provider.lower())
                or PROVIDER_REGISTRY.get(canon)
                or PROVIDER_REGISTRY.get(provider.lower())
            )
            model = meta.default_model if meta else "default"

        run_name = run_item.name or f"{provider}_{model}_{idx}"

        # Substring filter match
        if filter_str:
            tags_list = run_item.tags or []
            target_str = f"{run_name} {provider} {raw_provider} {model} {' '.join(tags_list)}".lower()
            if filter_str not in target_str:
                continue

        # Resolve API Key
        # Precedence: run_item.api_key -> CLI override -> batch_config.api_keys -> env var
        api_key = run_item.api_key
        if not api_key and overrides.get("api_key"):
            api_key = overrides.get("api_key")
        if not api_key:
            key_candidates = get_provider_key_candidates(provider) + get_provider_key_candidates(raw_provider)
            for candidate in key_candidates:
                if candidate in batch_config.api_keys and batch_config.api_keys[candidate]:
                    api_key = batch_config.api_keys[candidate]
                    break
        if not api_key:
            api_key = get_api_key_for_provider(provider) or get_api_key_for_provider(raw_provider)

        # Resolve Base URL
        # Precedence: run_item.base_url -> CLI override -> batch_config.base_urls -> registry default
        base_url = run_item.base_url
        if not base_url and overrides.get("base_url"):
            base_url = overrides.get("base_url")
        if not base_url:
            url_candidates = get_provider_key_candidates(provider) + get_provider_key_candidates(raw_provider)
            for candidate in url_candidates:
                if candidate in batch_config.base_urls and batch_config.base_urls[candidate]:
                    base_url = batch_config.base_urls[candidate]
                    break
        if not base_url:
            canon = CANONICAL_PROVIDER_MAP.get(raw_provider.lower(), raw_provider.lower())
            meta = (
                PROVIDER_REGISTRY.get(provider.lower())
                or PROVIDER_REGISTRY.get(raw_provider.lower())
                or PROVIDER_REGISTRY.get(canon)
            )
            if meta:
                base_url = meta.default_base_url

        # Resolve turns
        if overrides.get("turns") is not None:
            num_turns = int(overrides["turns"])
        elif run_item.num_turns is not None:
            num_turns = run_item.num_turns
        else:
            num_turns = int(defaults.get("num_turns", 3))

        # Resolve prompt
        if overrides.get("prompt") is not None:
            prompt = str(overrides["prompt"])
        elif run_item.prompt is not None:
            prompt = run_item.prompt
        else:
            prompt = str(defaults.get("prompt", "Generate a random integer. Do NOT output anything else."))

        # Resolve system prompt
        system_prompt = run_item.system_prompt if run_item.system_prompt is not None else defaults.get("system_prompt")
        if overrides.get("system_prompt") is not None:
            system_prompt = overrides["system_prompt"]

        # Resolve thinking
        if overrides.get("thinking") is not None:
            enable_thinking = bool(overrides["thinking"])
        elif run_item.enable_thinking is not None:
            enable_thinking = run_item.enable_thinking
        else:
            enable_thinking = bool(defaults.get("enable_thinking", True))

        # Resolve thinking_level (e.g. "max", "xhigh", "high", "medium", "low")
        thinking_level = None
        if overrides.get("thinking_level") is not None:
            thinking_level = str(overrides["thinking_level"]).strip().lower()
        elif run_item.thinking_level is not None:
            thinking_level = str(run_item.thinking_level).strip().lower()
        elif defaults.get("thinking_level") is not None:
            thinking_level = str(defaults["thinking_level"]).strip().lower()
        else:
            # Auto-infer from run name or model name if specified like (max), (high), (xhigh), (medium), (low)
            check_str = f"{run_name} {model}".lower()
            if "(max" in check_str or "(max)" in check_str:
                thinking_level = "max"
            elif "(xhigh" in check_str or "(xhigh)" in check_str:
                thinking_level = "xhigh"
            elif "(high" in check_str or "(high)" in check_str:
                thinking_level = "high"
            elif "(medium" in check_str or "(medium)" in check_str:
                thinking_level = "medium"
            elif "(low" in check_str or "(low)" in check_str:
                thinking_level = "low"

        # If thinking_level was explicitly or implicitly found and enable_thinking was not explicitly disabled, turn it on
        if thinking_level and run_item.enable_thinking is None and overrides.get("thinking") is None:
            enable_thinking = True

        # Thinking budget
        level_budget_defaults = {
            "max": 32000,
            "xhigh": 24000,
            "high": 16000,
            "medium": 8192,
            "low": 2048,
        }
        if overrides.get("thinking_budget") is not None:
            thinking_budget = int(overrides["thinking_budget"])
        elif run_item.thinking_budget is not None:
            thinking_budget = run_item.thinking_budget
        elif thinking_level in level_budget_defaults:
            thinking_budget = level_budget_defaults[thinking_level]
        else:
            thinking_budget = defaults.get("thinking_budget", 1024)

        # Caching
        if overrides.get("cache") is not None:
            enable_caching = bool(overrides["cache"])
        elif run_item.enable_caching is not None:
            enable_caching = run_item.enable_caching
        else:
            enable_caching = bool(defaults.get("enable_caching", True))

        # Local cache
        if overrides.get("use_local_cache") is not None:
            use_local_cache = bool(overrides["use_local_cache"])
        elif run_item.use_local_cache is not None:
            use_local_cache = run_item.use_local_cache
        else:
            use_local_cache = bool(defaults.get("use_local_cache", False))

        # Temperature
        temperature = (
            overrides["temperature"]
            if overrides.get("temperature") is not None
            else (run_item.temperature if run_item.temperature is not None else defaults.get("temperature", 1.0))
        )

        # Max tokens
        max_tokens = (
            overrides["max_tokens"]
            if overrides.get("max_tokens") is not None
            else (run_item.max_tokens if run_item.max_tokens is not None else defaults.get("max_tokens", 2048))
        )

        # Merge extra headers and extra body
        extra_headers = dict(defaults.get("extra_headers", {}))
        extra_headers.update(run_item.extra_headers)

        extra_body = dict(defaults.get("extra_body", {}))
        extra_body.update(run_item.extra_body)

        bench_config = BenchmarkConfig(
            name=run_name,
            provider=provider,
            model=model,
            num_turns=num_turns,
            prompt=prompt,
            system_prompt=system_prompt,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            temperature=temperature,
            top_p=run_item.top_p if run_item.top_p is not None else defaults.get("top_p"),
            seed=run_item.seed if run_item.seed is not None else defaults.get("seed"),
            max_tokens=max_tokens,
            enable_caching=enable_caching,
            use_local_cache=use_local_cache,
            local_cache_dir=run_item.local_cache_dir or defaults.get("local_cache_dir", ".rsi_cache"),
            timeout_seconds=run_item.timeout_seconds if run_item.timeout_seconds is not None else defaults.get("timeout_seconds", 90.0),
            max_retries=run_item.max_retries if run_item.max_retries is not None else defaults.get("max_retries", 3),
            api_key=api_key,
            base_url=base_url,
            extra_headers=extra_headers,
            extra_body=extra_body,
            tags=run_item.tags,
        )
        configs.append((run_name, bench_config))

    return configs


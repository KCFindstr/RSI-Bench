"""Tests for 28 OpenRouter models configuration in config.example.yaml and config.yaml."""

from pathlib import Path
import pytest
import yaml

from rsi_bench.config import (
    build_benchmark_configs,
    load_batch_config,
)
from rsi_bench.models import BatchConfig


REPO_ROOT = Path(__file__).parent.parent
CONFIG_EXAMPLE_PATH = REPO_ROOT / "config.example.yaml"
CONFIG_ACTIVE_PATH = REPO_ROOT / "config.yaml"


EXPECTED_28_MODELS = [
    "Claude Opus 5.5 (max with fallback)",
    "GPT-6 Astra (max)",
    "GPT-6.1 Sol (max)",
    "Claude Sonnet 5.5 (max with fallback)",
    "GPT-6.1 Terra (max)",
    "Gemini 4 Argon (high)",
    # Muse Wonder Full (max) is omitted!
    "Claude Fable 5.1 (max with fallback)",
    "Kimi K3.1 Pro",
    "Muse Wonder (max)",
    "Claude Haiku 5.5 (max)",
    "Grok 4.7 (xhigh)",
    "Qwen3.8 Max (0902)",
    "DeepSeek V4.1 Flash 1017 (max)",
    "GLM-5.3 (max)",
    "Gemini 3.8 Flash (high)",
    "MiMo-V2.6-Pro",
    "Ling 3.1 Flash 1019",
    "MiniMax-M3.1-Flash",
    "Step 5 Preview",
    "GPT-6 Luna (max)",
    "Mistral Large 4 Preview",
    "Muse Spark Open (xhigh)",
    "Qwen3.8 27B (xhigh)",
    "K2 Horizon 375B A23B",
    "Beam 1.0",
    "Nemotron 3.5 Super VL",
    "Inkling (xhigh)",
    "Muse Glimmer (high)",
]


def test_config_example_yaml_has_all_28_public_models():
    """Verify config.example.yaml contains all 28 models with public APIs via OpenRouter."""
    assert CONFIG_EXAMPLE_PATH.is_file()
    cfg: BatchConfig = load_batch_config(CONFIG_EXAMPLE_PATH)

    # Exclude mock simulation run
    configured_runs = [r for r in cfg.runs if r.provider != "mock"]
    assert len(configured_runs) == 28

    run_names = [r.name for r in configured_runs]
    assert run_names == EXPECTED_28_MODELS

    # Muse Wonder Full (max) must NOT be present (no public API)
    for name in run_names:
        assert "Muse Wonder Full" not in name

    # All 28 models must use OpenRouter
    for r in configured_runs:
        assert r.provider == "openrouter"
        assert r.model is not None
        assert "/" in r.model, f"Expected OpenRouter model format 'provider/model', got {r.model}"

    # OpenRouter API key mapping exists
    assert "openrouter" in cfg.api_keys


def test_config_yaml_has_all_28_public_models():
    """Verify config.yaml contains all 28 models configured via OpenRouter."""
    assert CONFIG_ACTIVE_PATH.is_file()
    cfg: BatchConfig = load_batch_config(CONFIG_ACTIVE_PATH)

    configured_runs = [r for r in cfg.runs if r.provider != "mock"]
    assert len(configured_runs) == 28

    run_names = [r.name for r in configured_runs]
    assert run_names == EXPECTED_28_MODELS

    for r in configured_runs:
        assert r.provider == "openrouter"
        assert r.model is not None
        assert "/" in r.model


def test_config_yaml_mock_simulation_execution():
    """Verify all 28 models in config.yaml can be converted to mock runs for testing."""
    cfg: BatchConfig = load_batch_config(CONFIG_ACTIVE_PATH)

    # Simulate --mock override
    benchmark_configs = build_benchmark_configs(cfg, cli_overrides={"mock": True})
    assert len(benchmark_configs) == 29  # 1 mock + 28 models

    for run_name, b_cfg in benchmark_configs:
        assert b_cfg.provider == "mock"
        assert b_cfg.num_turns >= 1

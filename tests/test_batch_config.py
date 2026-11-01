"""Tests for batch configuration loading, precedence, and execution."""

import json
import os
from pathlib import Path
import pytest
import yaml

from rsi_bench.cli import main
from rsi_bench.config import (
    _expand_env_vars,
    build_benchmark_configs,
    find_default_config_path,
    load_batch_config,
    parse_batch_config_data,
)
from rsi_bench.models import BatchConfig, BatchRunItem
from rsi_bench.runner import run_batch
from rsi_bench.storage import StorageManager


@pytest.fixture
def temp_output_dir(tmp_path):
    out = tmp_path / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def test_load_batch_config_json(tmp_path):
    cfg_file = tmp_path / "test_config.json"
    data = {
        "version": "1",
        "output_dir": "custom_results",
        "defaults": {
            "num_turns": 4,
            "enable_thinking": True,
        },
        "api_keys": {
            "mock": "mock-key-123",
            "anthropic": "ant-key-456",
        },
        "runs": [
            {
                "name": "run-1",
                "provider": "mock",
                "turns": 2,
            },
            {
                "name": "run-2",
                "provider": "anthropic",
                "model": "claude-3-7-sonnet-20250219",
                "thinking": False,
            },
        ],
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    batch_cfg = load_batch_config(cfg_file)
    assert batch_cfg.output_dir == "custom_results"
    assert batch_cfg.api_keys["mock"] == "mock-key-123"
    assert len(batch_cfg.runs) == 2
    assert batch_cfg.runs[0].name == "run-1"
    assert batch_cfg.runs[0].num_turns == 2
    assert batch_cfg.runs[1].enable_thinking is False


def test_load_batch_config_yaml(tmp_path):
    cfg_file = tmp_path / "test_config.yaml"
    yaml_content = """
version: "1"
output_dir: "yaml_results"
defaults:
  turns: 5
  cache: false
runs:
  - name: "yaml-mock"
    provider: "mock"
"""
    cfg_file.write_text(yaml_content, encoding="utf-8")

    batch_cfg = load_batch_config(cfg_file)
    assert batch_cfg.output_dir == "yaml_results"
    assert batch_cfg.defaults["num_turns"] == 5
    assert batch_cfg.defaults["enable_caching"] is False
    assert len(batch_cfg.runs) == 1
    assert batch_cfg.runs[0].name == "yaml-mock"


def test_load_batch_config_list_format(tmp_path):
    cfg_file = tmp_path / "list_config.json"
    data = [
        {"provider": "mock", "turns": 1, "name": "first"},
        {"provider": "mock", "turns": 2, "name": "second"},
    ]
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    batch_cfg = load_batch_config(cfg_file)
    assert len(batch_cfg.runs) == 2
    assert batch_cfg.runs[0].name == "first"
    assert batch_cfg.runs[1].num_turns == 2


def test_config_env_var_expansion(monkeypatch):
    monkeypatch.setenv("TEST_KEY_ALPHA", "alpha-secret-999")
    monkeypatch.setenv("TEST_BASE_URL", "http://test-server:8000/v1")

    raw = {
        "api_keys": {
            "p1": "${TEST_KEY_ALPHA}",
            "p2": "$TEST_KEY_ALPHA",
            "p3": "env:TEST_KEY_ALPHA",
            "p4": "env(TEST_KEY_ALPHA)",
        },
        "base_urls": {
            "p1": "${TEST_BASE_URL}",
        },
    }
    expanded = _expand_env_vars(raw)
    assert expanded["api_keys"]["p1"] == "alpha-secret-999"
    assert expanded["api_keys"]["p2"] == "alpha-secret-999"
    assert expanded["api_keys"]["p3"] == "alpha-secret-999"
    assert expanded["api_keys"]["p4"] == "alpha-secret-999"
    assert expanded["base_urls"]["p1"] == "http://test-server:8000/v1"


def test_api_key_resolution_precedence(monkeypatch):
    monkeypatch.setenv("MOCK_API_KEY", "env-key")

    # 1. Environment variable fallback
    batch_cfg1 = BatchConfig(
        runs=[BatchRunItem(provider="mock", name="run1")]
    )
    configs = build_benchmark_configs(batch_cfg1)
    assert configs[0][1].api_key == "env-key"

    # 2. Batch-level key overrides environment
    batch_cfg2 = BatchConfig(
        api_keys={"mock": "batch-key"},
        runs=[BatchRunItem(provider="mock", name="run1")]
    )
    configs = build_benchmark_configs(batch_cfg2)
    assert configs[0][1].api_key == "batch-key"

    # 3. CLI override takes precedence over batch and env
    configs = build_benchmark_configs(batch_cfg2, cli_overrides={"api_key": "cli-key"})
    assert configs[0][1].api_key == "cli-key"

    # 4. Run-level key overrides all
    batch_cfg3 = BatchConfig(
        api_keys={"mock": "batch-key"},
        runs=[BatchRunItem(provider="mock", name="run1", api_key="run-level-key")]
    )
    configs = build_benchmark_configs(batch_cfg3, cli_overrides={"api_key": "cli-key"})
    assert configs[0][1].api_key == "run-level-key"


def test_base_url_resolution_precedence():
    # 1. Registry default for deepseek
    batch_cfg1 = BatchConfig(
        runs=[BatchRunItem(provider="deepseek", name="ds1")]
    )
    configs = build_benchmark_configs(batch_cfg1)
    assert configs[0][1].base_url == "https://api.deepseek.com"

    # 2. Batch-level base_urls
    batch_cfg2 = BatchConfig(
        base_urls={"deepseek": "https://custom.deepseek.proxy/v1"},
        runs=[BatchRunItem(provider="deepseek", name="ds1")]
    )
    configs = build_benchmark_configs(batch_cfg2)
    assert configs[0][1].base_url == "https://custom.deepseek.proxy/v1"

    # 3. CLI override
    configs = build_benchmark_configs(batch_cfg2, cli_overrides={"base_url": "https://cli.proxy/v1"})
    assert configs[0][1].base_url == "https://cli.proxy/v1"

    # 4. Run-level URL overrides
    batch_cfg3 = BatchConfig(
        base_urls={"deepseek": "https://custom.deepseek.proxy/v1"},
        runs=[BatchRunItem(provider="deepseek", name="ds1", base_url="https://run.proxy/v1")]
    )
    configs = build_benchmark_configs(batch_cfg3, cli_overrides={"base_url": "https://cli.proxy/v1"})
    assert configs[0][1].base_url == "https://run.proxy/v1"


def test_defaults_propagation_and_aliases():
    raw_dict = {
        "defaults": {
            "turns": 4,
            "prompt": "Custom batch prompt",
            "thinking": False,
            "thinking_budget": 512,
            "cache": False,
            "local_cache": True,
            "temperature": 0.7,
            "max_tokens": 1024,
        },
        "runs": [
            {
                "name": "run-default",
                "provider": "mock",
            },
            {
                "name": "run-override",
                "provider": "mock",
                "turns": 1,
                "thinking": True,
                "temperature": 0.2,
            },
        ],
    }
    batch_cfg = parse_batch_config_data(raw_dict)
    configs = build_benchmark_configs(batch_cfg)

    # run-default inherits all defaults
    _, cfg0 = configs[0]
    assert cfg0.num_turns == 4
    assert cfg0.prompt == "Custom batch prompt"
    assert cfg0.enable_thinking is False
    assert cfg0.thinking_budget == 512
    assert cfg0.enable_caching is False
    assert cfg0.use_local_cache is True
    assert cfg0.temperature == 0.7
    assert cfg0.max_tokens == 1024

    # run-override selectively overrides defaults
    _, cfg1 = configs[1]
    assert cfg1.num_turns == 1
    assert cfg1.enable_thinking is True
    assert cfg1.temperature == 0.2
    assert cfg1.max_tokens == 1024


def test_disabled_runs_are_skipped():
    batch_cfg = BatchConfig(
        runs=[
            BatchRunItem(name="enabled-1", provider="mock", enabled=True),
            BatchRunItem(name="disabled-2", provider="mock", enabled=False),
            BatchRunItem(name="enabled-3", provider="mock", enabled=True),
        ]
    )
    configs = build_benchmark_configs(batch_cfg)
    assert len(configs) == 2
    assert [name for name, _ in configs] == ["enabled-1", "enabled-3"]


def test_filter_runs_by_substring():
    batch_cfg = BatchConfig(
        runs=[
            BatchRunItem(name="fast-mock-1", provider="mock", tags=["fast"]),
            BatchRunItem(name="slow-mock-2", provider="mock", tags=["slow"]),
            BatchRunItem(name="fast-mock-3", provider="mock", tags=["fast", "special"]),
        ]
    )
    # Filter by name substring
    configs = build_benchmark_configs(batch_cfg, cli_overrides={"filter": "slow"})
    assert len(configs) == 1
    assert configs[0][0] == "slow-mock-2"

    # Filter by tag substring
    configs_fast = build_benchmark_configs(batch_cfg, cli_overrides={"filter": "fast"})
    assert len(configs_fast) == 2


def test_find_default_config_path(tmp_path):
    # None found initially
    assert find_default_config_path(tmp_path) is None

    # Found when config.yaml exists
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("runs: []", encoding="utf-8")
    assert find_default_config_path(tmp_path) == yaml_file

    # Priority check: config.yaml takes precedence over config.json
    json_file = tmp_path / "config.json"
    json_file.write_text("{}", encoding="utf-8")
    assert find_default_config_path(tmp_path) == yaml_file


def test_run_batch_execution(temp_output_dir):
    batch_cfg = BatchConfig(
        output_dir=str(temp_output_dir),
        runs=[
            BatchRunItem(name="batch-mock-1", provider="mock", num_turns=2),
            BatchRunItem(name="batch-mock-2", provider="mock", num_turns=3),
        ],
    )
    storage = StorageManager(output_dir=str(temp_output_dir))

    batch_result = run_batch(
        batch_config=batch_cfg,
        output_dir=str(temp_output_dir),
        storage_manager=storage,
    )

    assert batch_result.total_runs == 2
    assert batch_result.completed_runs == 2
    assert batch_result.successful_runs == 2
    assert batch_result.failed_runs == 0
    assert batch_result.all_successful is True
    assert len(batch_result.results) == 2

    # Check that batch JSON and Markdown exist on disk
    batch_json = temp_output_dir / f"batch_{batch_result.batch_id}.json"
    batch_md = temp_output_dir / f"batch_{batch_result.batch_id}.md"
    summary_csv = temp_output_dir / "benchmark_summary.csv"

    assert batch_json.is_file()
    assert batch_md.is_file()
    assert summary_csv.is_file()

    # Verify individual traces exist
    traces = list((temp_output_dir / "traces").glob("*.json"))
    assert len(traces) == 2


def test_run_batch_isolation_on_failure(temp_output_dir):
    batch_cfg = BatchConfig(
        output_dir=str(temp_output_dir),
        runs=[
            BatchRunItem(name="valid-mock", provider="mock", num_turns=2),
            BatchRunItem(name="invalid-provider", provider="non_existent_provider_xyz", num_turns=2),
            BatchRunItem(name="valid-mock-2", provider="mock", num_turns=2),
        ],
    )
    storage = StorageManager(output_dir=str(temp_output_dir))

    batch_result = run_batch(
        batch_config=batch_cfg,
        output_dir=str(temp_output_dir),
        storage_manager=storage,
    )

    assert batch_result.total_runs == 3
    assert batch_result.completed_runs == 3
    assert batch_result.successful_runs == 2
    assert batch_result.failed_runs == 1
    assert batch_result.all_successful is False

    # Check error was recorded for the 2nd run
    failed_run = batch_result.results[1]
    assert failed_run.all_valid is False
    assert "non_existent_provider_xyz" in (failed_run.error or "")


def test_cli_batch_execution(tmp_path):
    cfg_file = tmp_path / "cli_test_config.yaml"
    cfg_file.write_text("""
output_dir: "{}"
runs:
  - name: "cli-mock-1"
    provider: "mock"
    turns: 2
  - name: "cli-mock-2"
    provider: "mock"
    turns: 1
""".format(str(tmp_path / "cli_results").replace("\\", "/")), encoding="utf-8")

    code = main(["--config", str(cfg_file)])
    assert code == 0


def test_cli_batch_mock_override(tmp_path):
    # Provider specified as anthropic (which has no key), but --mock forces mock provider
    cfg_file = tmp_path / "cli_mock_override.json"
    data = {
        "output_dir": str(tmp_path / "mock_override_results"),
        "runs": [
            {"name": "override-run", "provider": "anthropic", "turns": 2}
        ],
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    code = main(["-c", str(cfg_file), "--mock"])
    assert code == 0


def test_cli_filter_flag(tmp_path):
    cfg_file = tmp_path / "filter_config.yaml"
    cfg_file.write_text("""
output_dir: "{}"
runs:
  - name: "target-run"
    provider: "mock"
    turns: 1
  - name: "other-run"
    provider: "non_existent_should_not_run"
    turns: 1
""".format(str(tmp_path / "filter_results").replace("\\", "/")), encoding="utf-8")

    code = main(["-c", str(cfg_file), "--filter", "target-run"])
    assert code == 0


def test_env_var_default_and_bare_dollar_safety(monkeypatch):
    monkeypatch.setenv("SET_ENV_VAR", "actual_val")

    raw = {
        "with_default": "${UNSET_VAR_XYZ:-my_default_value}",
        "with_set": "${SET_ENV_VAR:-fallback}",
        "env_colon_default": "env:UNSET_COLON_VAR:-colon_fallback",
        "bare_dollar_price": "Total cost is $100 and item 2 is $50",
        "escaped_dollar": "$$LITERAL_NAME",
    }
    expanded = _expand_env_vars(raw)
    assert expanded["with_default"] == "my_default_value"
    assert expanded["with_set"] == "actual_val"
    assert expanded["env_colon_default"] == "colon_fallback"
    assert expanded["bare_dollar_price"] == "Total cost is $100 and item 2 is $50"
    assert expanded["escaped_dollar"] == "$LITERAL_NAME"


def test_provider_family_and_alias_key_resolution():
    batch_cfg = BatchConfig(
        api_keys={
            "openai": "sk-shared-openai-key",
            "gemini": "shared-gemini-key",
            "anthropic": "shared-anthropic-key",
        },
        runs=[
            BatchRunItem(name="chat", provider="openai_chat"),
            BatchRunItem(name="responses", provider="openai_responses"),
            BatchRunItem(name="completion", provider="openai_completion"),
            BatchRunItem(name="interactions", provider="gemini_interactions"),
            BatchRunItem(name="claude", provider="claude"),
        ],
    )
    configs = dict(build_benchmark_configs(batch_cfg))
    assert configs["chat"].api_key == "sk-shared-openai-key"
    assert configs["responses"].api_key == "sk-shared-openai-key"
    assert configs["completion"].api_key == "sk-shared-openai-key"
    assert configs["interactions"].api_key == "shared-gemini-key"
    assert configs["claude"].api_key == "shared-anthropic-key"


def test_colon_in_model_name_creates_valid_file(temp_output_dir):
    from rsi_bench.models import BenchmarkResult
    storage = StorageManager(output_dir=str(temp_output_dir))

    res = BenchmarkResult(
        run_id="run_colon",
        provider="generic_openai",
        model="llama3.3:70b",
        num_turns_requested=1,
        num_turns_completed=1,
        all_valid=True,
    )
    json_path = storage.save_result(res)

    assert ":" not in json_path.name
    assert "llama3.3_70b" in json_path.name
    assert json_path.is_file()

    # Check Markdown report
    md_path = storage.traces_dir / f"generic_openai_llama3.3_70b_run_colon.md"
    assert md_path.is_file()


def test_markdown_report_includes_error_message(temp_output_dir):
    from rsi_bench.models import BenchmarkResult
    storage = StorageManager(output_dir=str(temp_output_dir))

    res = BenchmarkResult(
        run_id="run_err",
        provider="mock",
        model="default",
        num_turns_requested=2,
        num_turns_completed=0,
        all_valid=False,
        error="Authentication failure: invalid token",
    )
    storage.save_result(res)

    md_path = storage.traces_dir / "mock_default_run_err.md"
    assert md_path.is_file()
    md_content = md_path.read_text(encoding="utf-8")
    assert "Authentication failure: invalid token" in md_content
    assert "- **Error:** `Authentication failure: invalid token`" in md_content


def test_cli_batch_output_dir_from_config(tmp_path):
    custom_out = tmp_path / "custom_batch_output"
    cfg_file = tmp_path / "custom_dir_config.yaml"
    cfg_file.write_text(f"""
output_dir: "{str(custom_out).replace('\\', '/')}"
runs:
  - name: "custom-out-mock"
    provider: "mock"
    turns: 1
""", encoding="utf-8")

    code = main(["-c", str(cfg_file)])
    assert code == 0
    assert custom_out.is_dir()
    traces = list((custom_out / "traces").glob("*.json"))
    assert len(traces) == 1


def test_cli_batch_overrides_temperature_and_turns(tmp_path):
    custom_out = tmp_path / "override_output"
    cfg_file = tmp_path / "override_config.yaml"
    cfg_file.write_text(f"""
output_dir: "{str(custom_out).replace('\\', '/')}"
defaults:
  turns: 3
  temperature: 0.9
runs:
  - name: "cli-override-mock"
    provider: "mock"
""", encoding="utf-8")

    code = main(["-c", str(cfg_file), "--turns", "1", "--temperature", "0.2"])
    assert code == 0
    traces = list((custom_out / "traces").glob("*.json"))
    assert len(traces) == 1
    trace_data = json.loads(traces[0].read_text(encoding="utf-8"))
    assert trace_data["num_turns_requested"] == 1
    assert trace_data["config"]["temperature"] == 0.2


def test_cli_filter_with_mock_triggers_batch(tmp_path):
    custom_out = tmp_path / "filter_mock_output"
    cfg_file = tmp_path / "filter_mock_config.yaml"
    cfg_file.write_text(f"""
output_dir: "{str(custom_out).replace('\\', '/')}"
runs:
  - name: "target-mock"
    provider: "anthropic"
    turns: 1
  - name: "other-run"
    provider: "deepseek"
    turns: 1
""", encoding="utf-8")

    # anthropic has no key, but --mock turns it into a mock run and filter only runs target-mock
    code = main(["-c", str(cfg_file), "--filter", "target-mock", "--mock"])
    assert code == 0
    traces = list((custom_out / "traces").glob("*.json"))
    assert len(traces) == 1
    trace_data = json.loads(traces[0].read_text(encoding="utf-8"))
    assert trace_data["config"]["name"] == "target-mock"
    assert trace_data["provider"] == "mock"


def test_string_tags_parsed_to_list():
    raw = {
        "runs": [
            {"provider": "mock", "tags": "fast, test, mock"},
        ]
    }
    batch_cfg = parse_batch_config_data(raw)
    assert batch_cfg.runs[0].tags == ["fast", "test", "mock"]


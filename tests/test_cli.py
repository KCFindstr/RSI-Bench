"""Tests for CLI arguments and execution."""

import pytest
from rsi_bench.cli import main


def test_cli_mock_run():
    exit_code = main(["--mock", "--turns", "2"])
    assert exit_code == 0


def test_cli_list_providers():
    exit_code = main(["--list-providers"])
    assert exit_code == 0


def test_cli_clear_cache():
    exit_code = main(["--clear-cache"])
    assert exit_code == 0

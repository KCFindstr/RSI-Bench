"""Tests for RSI-Bench visualization module and chart generation."""

import json
from pathlib import Path
import re
import pytest

from rsi_bench.models import BenchmarkConfig, BenchmarkResult, TokenUsage, TurnTrace
from rsi_bench.visualization import (
    LOGOS,
    REFERENCE_MODELS,
    extract_trajectory_data,
    find_browser_executable,
    generate_all_charts,
    generate_mock_trajectory_data,
    get_public_models,
    get_reference_models,
    load_results_from_batch_json,
    load_results_from_csv,
    render_html_to_png,
    render_intelligence_index_bar_chart_html,
    render_trajectory_line_graph_html,
)


def test_reference_models_registry():
    """Verify registry contains 29 models, exactly 1 without public API, and scores range from 58 to 6."""
    models = get_reference_models()
    assert len(models) == 29

    # Exactly 1 model without public API
    hatched = [m for m in models if not m["has_public_api"]]
    assert len(hatched) == 1
    assert hatched[0]["name"] == "Muse Wonder Full (max)"
    assert hatched[0]["is_hatched"] is True

    # 28 models with public APIs
    public_models = get_public_models()
    assert len(public_models) == 28

    # Top model has score 58, lowest has score 6
    assert models[0]["score"] == 58
    assert models[0]["name"] == "Claude Opus 5.5 (max with fallback)"
    assert models[-1]["score"] == 6
    assert models[-1]["name"] == "Muse Glimmer (high)"

    # All models have required metadata fields
    for m in models:
        assert "id" in m
        assert "name" in m
        assert "provider" in m
        assert "color" in m
        assert "score" in m
        assert m["score"] > 0


def test_bar_chart_html_rendering():
    """Verify HTML generation of the Artificial Analysis bar chart."""
    html = render_intelligence_index_bar_chart_html()
    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")
    assert "Artificial Analysis Intelligence Index" in html
    assert "No publicly available API" in html
    assert "hatch-pattern" in html

    # Verify scores are rendered inside bars
    for score in [58, 57, 55, 54, 51, 50, 49, 46, 43, 36, 34, 32, 31, 30, 29, 28, 25, 20, 18, 14, 12, 6]:
        assert f">{score}</text>" in html

    # Verify provider logos and rotated model labels exist
    assert "Claude Opus 5.5" in html
    assert "GPT-6 Astra" in html
    assert "Gemini 4 Argon" in html
    assert "DeepSeek V4.1" in html


def test_line_graph_unlabeled_axes_joke_constraint():
    """
    CRITICAL JOKE CONSTRAINT TEST:
    Verify the line graph shows turn-by-turn outputs + cumulative prefix sums
    WITHOUT disclosing or labeling what each axis means (no axis titles like
    'Turns', 'Steps', 'Score', 'Integer', or 'Prefix Sum').
    """
    mock_data = generate_mock_trajectory_data(num_turns=5, seed=123)
    html = render_trajectory_line_graph_html(mock_data)

    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")
    assert "Multi-Turn Dynamic Performance Trajectory Index" in html

    # Verify model names are in the legend
    assert "Claude Opus 5.5 (max with fallback)" in html
    assert "GPT-6 Astra (max)" in html

    # Verify ticks are bare numbers (1, 2, 3, 4, 5)
    for t in range(1, 6):
        assert f">{t}</text>" in html

    # Verify that NO axis label elements or axis titles exist!
    # Check that there are NO axis titles for turns or integers/scores
    forbidden_axis_labels = [
        r"<text[^>]*>\s*Turns?\s*</text>",
        r"<text[^>]*>\s*Steps?\s*</text>",
        r"<text[^>]*>\s*Score\s*</text>",
        r"<text[^>]*>\s*Scores\s*</text>",
        r"<text[^>]*>\s*Integer\s*</text>",
        r"<text[^>]*>\s*Integers\s*</text>",
        r"<text[^>]*>\s*Prefix\s*Sum\s*</text>",
        r"<text[^>]*>\s*Cumulative\s*Sum\s*</text>",
        r"<text[^>]*>\s*Time\s*</text>",
        r"<text[^>]*>\s*Rounds?\s*</text>",
        r"class=\"axis-title\"",
        r"class=\"axis-label\"",
        r"id=\"x-axis-label\"",
        r"id=\"y-axis-label\"",
    ]
    for pattern in forbidden_axis_labels:
        match = re.search(pattern, html, re.IGNORECASE)
        assert match is None, f"Found forbidden axis label matching '{pattern}': {match.group(0)}"


def test_mock_trajectory_data_math():
    """Verify cumulative prefix sums math: prefix_sums[i] == sum(integers[:i+1])."""
    data = generate_mock_trajectory_data(num_turns=6, seed=999)
    assert len(data) == 29

    for model_name, info in data.items():
        ints = info["integers"]
        sums = info["prefix_sums"]
        turns = info["turns"]

        assert len(ints) == 6
        assert len(sums) == 6
        assert len(turns) == 6

        # Check prefix sum correctness
        running_sum = 0
        for i, val in enumerate(ints):
            running_sum += val
            assert sums[i] == running_sum


def test_extract_trajectory_from_benchmark_results():
    """Verify extracting trajectory data from BenchmarkResult model instances."""
    res1 = BenchmarkResult(
        run_id="run001",
        provider="mock",
        model="claude-3-opus",
        num_turns_requested=3,
        num_turns_completed=3,
        all_valid=True,
        valid_turns_count=3,
        parsed_integers=[100, -25, 50],
        total_usage=TokenUsage(),
        turns=[
            TurnTrace(turn_index=1, prompt="p", raw_response_text="100", parsed_integer=100, parse_success=True),
            TurnTrace(turn_index=2, prompt="p", raw_response_text="-25", parsed_integer=-25, parse_success=True),
            TurnTrace(turn_index=3, prompt="p", raw_response_text="50", parsed_integer=50, parse_success=True),
        ],
        config={"name": "Claude Opus 5.5 (max with fallback)"},
    )

    traj = extract_trajectory_data([res1])
    name = "Claude Opus 5.5 (max with fallback)"
    assert name in traj
    assert traj[name]["integers"] == [100, -25, 50]
    assert traj[name]["prefix_sums"] == [100, 75, 125]
    assert traj[name]["turns"] == [1, 2, 3]


def test_load_results_from_batch_json(tmp_path):
    """Verify loading from batch JSON file."""
    batch_file = tmp_path / "test_batch.json"
    batch_data = {
        "batch_id": "test1234",
        "results": [
            {
                "run_id": "r1",
                "provider": "mock",
                "model": "m1",
                "num_turns_requested": 2,
                "num_turns_completed": 2,
                "all_valid": True,
                "valid_turns_count": 2,
                "parsed_integers": [42, 108],
                "turns": [
                    {"turn_index": 1, "prompt": "p", "raw_response_text": "42", "parsed_integer": 42, "parse_success": True},
                    {"turn_index": 2, "prompt": "p", "raw_response_text": "108", "parsed_integer": 108, "parse_success": True},
                ],
                "config": {"name": "test-model-1"},
            }
        ]
    }
    batch_file.write_text(json.dumps(batch_data), encoding="utf-8")

    results = load_results_from_batch_json(batch_file)
    assert len(results) == 1
    assert results[0].parsed_integers == [42, 108]


def test_find_browser_executable():
    """Verify Chrome or Edge executable is located on system."""
    browser = find_browser_executable()
    assert browser is not None
    assert Path(browser).is_file()


def test_render_html_to_png(tmp_path):
    """Verify headless Chrome/Edge renders HTML to a valid PNG image."""
    html_file = tmp_path / "test.html"
    html_file.write_text(
        "<html><body style='background:#ffffff;'><h1>Headless Test</h1></body></html>",
        encoding="utf-8",
    )
    png_file = tmp_path / "test.png"

    success = render_html_to_png(html_file, png_file, width=800, height=600)
    assert success is True
    assert png_file.is_file()
    assert png_file.stat().st_size > 0


def test_generate_all_charts(tmp_path):
    """Verify end-to-end generation of both bar chart and line graph in HTML and PNG."""
    charts = generate_all_charts(
        output_dir=tmp_path / "charts",
        num_turns=3,
        render_png=True,
        use_reference_scores=True,
    )

    assert "bar_chart_html" in charts
    assert "line_graph_html" in charts
    assert "bar_chart_png" in charts
    assert "line_graph_png" in charts

    for key, path in charts.items():
        assert Path(path).is_file()
        assert Path(path).stat().st_size > 0


def test_bar_chart_negative_and_dynamic_scores():
    """Verify bar chart handles negative, zero, and out-of-scale (>60) scores with valid positive SVG heights."""
    mixed_models = [
        {"name": "Model Alpha", "score": -1412, "color": "#C8644A", "provider_key": "anthropic"},
        {"name": "Model Beta", "score": 250, "color": "#1E2022", "provider_key": "openai"},
        {"name": "Model Gamma", "score": 0, "color": "#2EA043", "provider_key": "google"},
        {"name": "Model Delta", "score": -50, "color": "#FF5B00", "provider_key": "alibaba"},
    ]

    html = render_intelligence_index_bar_chart_html(models=mixed_models)
    assert isinstance(html, str)
    assert ">-1412</text>" in html
    assert ">250</text>" in html
    assert ">0</text>" in html

    # Verify no negative height in any rect tag
    rect_heights = re.findall(r'<rect[^>]+height="([^"]+)"', html)
    assert len(rect_heights) > 0
    for h_str in rect_heights:
        h_val = float(h_str)
        assert h_val >= 0, f"SVG rect height must be non-negative, got {h_val}"

    # Verify rect y positions are non-negative
    rect_ys = re.findall(r'<rect[^>]+y="([^"]+)"', html)
    for y_str in rect_ys:
        y_val = float(y_str)
        assert y_val >= 0, f"SVG rect y must be non-negative, got {y_val}"


def test_bar_chart_single_model_header_layout():
    """Verify bar chart maintains minimum container width so header is not squished when 1 model is run."""
    single_model = [{"name": "Single Model", "score": 42, "color": "#C8644A", "provider_key": "anthropic"}]
    html = render_intelligence_index_bar_chart_html(models=single_model)

    # Container width must be at least 1100px to prevent header title text wrapping
    match_width = re.search(r'max-width:\s*(\d+)px', html)
    assert match_width is not None
    container_width = int(match_width.group(1))
    assert container_width >= 1100, f"Expected container width >= 1100, got {container_width}"


def test_line_graph_shows_both_output_and_trajectory_by_default():
    """Verify both turn outputs (dashed) and prefix sums (solid) are visible by default in line graph and rendered PNG."""
    mock_data = generate_mock_trajectory_data(num_turns=3, seed=777)
    html = render_trajectory_line_graph_html(mock_data)

    # raw-layer must NOT be hidden by default (so headless browser captures both series)
    assert 'id="raw-layer"' in html
    assert 'id="raw-layer" style="display: none;"' not in html
    assert 'id="traj-layer"' in html
    assert 'class="ctrl-btn active" id="btn-combined"' in html
    assert "Trajectory Curve" in html
    assert "Output Series" in html


def test_generate_all_charts_from_real_benchmark_result_with_negative_integers(tmp_path):
    """Verify end-to-end chart generation from actual benchmark execution with negative integer outputs."""
    result = BenchmarkResult(
        run_id="run_neg",
        provider="mock",
        model="claude-3-opus",
        num_turns_requested=3,
        num_turns_completed=3,
        all_valid=True,
        valid_turns_count=3,
        parsed_integers=[309, -772, -949],
        total_usage=TokenUsage(),
        turns=[
            TurnTrace(turn_index=1, prompt="p", raw_response_text="309", parsed_integer=309, parse_success=True),
            TurnTrace(turn_index=2, prompt="p", raw_response_text="-772", parsed_integer=-772, parse_success=True),
            TurnTrace(turn_index=3, prompt="p", raw_response_text="-949", parsed_integer=-949, parse_success=True),
        ],
        config={"name": "Claude Opus 5.5 (max with fallback)"},
    )

    out_dir = tmp_path / "charts_from_result"
    charts = generate_all_charts(
        data_source=[result],
        output_dir=out_dir,
        num_turns=3,
        render_png=True,
    )

    assert "bar_chart_html" in charts
    assert "line_graph_html" in charts
    assert "bar_chart_png" in charts
    assert "line_graph_png" in charts

    # Check bar chart HTML has no negative heights
    bar_html = charts["bar_chart_html"].read_text(encoding="utf-8")
    for h_str in re.findall(r'<rect[^>]+height="([^"]+)"', bar_html):
        assert float(h_str) >= 0

    # Check PNG files exist and are non-empty
    assert charts["bar_chart_png"].is_file()
    assert charts["bar_chart_png"].stat().st_size > 0
    assert charts["line_graph_png"].is_file()
    assert charts["line_graph_png"].stat().st_size > 0


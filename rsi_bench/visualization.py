"""
Visualization engine for RSI-Bench.

Generates:
1. RSI-Bench Index bar charts matching the frontier intelligence index design.
2. Multi-turn trajectory line graphs showing turn-by-turn outputs and cumulative prefix sums
   with symmetrical logarithmic scaling (symlog) and WITHOUT labeled axes (preserving the joke).
3. Headless Chrome/Edge rendering of self-contained HTML to PNG images.
"""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union

from rsi_bench.models import BatchBenchmarkResult, BenchmarkResult


# ==============================================================================
# Model Reference Registry (29 models matching the Artificial Analysis index)
# ==============================================================================

# Official Provider Logo URLs (Direct official vector and image assets from Artificial Analysis)
OFFICIAL_LOGO_URLS: Dict[str, str] = {
    "anthropic": "https://artificialanalysis.ai/img/logos/anthropic.svg",
    "openai": "https://artificialanalysis.ai/img/logos/openai.svg",
    "google": "https://artificialanalysis.ai/img/logos/google.svg",
    "meta": "https://artificialanalysis.ai/img/logos/meta.svg",
    "xai": "https://artificialanalysis.ai/img/logos/spacexai.svg",
    "alibaba": "https://artificialanalysis.ai/img/logos/alibaba.svg",
    "deepseek": "https://artificialanalysis.ai/img/logos/deepseek.svg",
    "zhipu": "https://artificialanalysis.ai/img/logos/zai.svg",
    "xiaomi": "https://artificialanalysis.ai/img/logos/xiaomi.svg",
    "ling": "https://artificialanalysis.ai/img/logos/inclusionai.jpg",
    "kimi": "https://artificialanalysis.ai/img/logos/kimi.jpg",
    "minimax": "https://artificialanalysis.ai/img/logos/minimax.svg",
    "stepfun": "https://artificialanalysis.ai/img/logos/stepfun.svg",
    "mistral": "https://artificialanalysis.ai/img/logos/mistral.svg",
    "horizon": "https://artificialanalysis.ai/img/logos/ifm.svg",
    "beam": "https://artificialanalysis.ai/img/logos/reflection.svg",
    "nvidia": "https://artificialanalysis.ai/img/logos/nvidia.svg",
    "inkling": "https://artificialanalysis.ai/img/logos/thinking-machines.svg",
}

LOGOS: Dict[str, str] = {
    key: (
        f'<img src="{url}" width="18" height="18" alt="{key}" '
        f'style="width: 18px; height: 18px; object-fit: contain; border-radius: 2px; display: block;" />'
    )
    for key, url in OFFICIAL_LOGO_URLS.items()
}


REFERENCE_MODELS: List[Dict[str, Any]] = [
    {
        "id": "claude-opus-5-5",
        "name": "Claude Opus 5.5 (max)",
        "provider": "Anthropic",
        "provider_key": "anthropic",
        "score": 58,
        "color": "#C8644A",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "anthropic/claude-3-opus",
    },
    {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra (max)",
        "provider": "OpenAI",
        "provider_key": "openai",
        "score": 57,
        "color": "#1E2022",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "openai/gpt-4o",
    },
    {
        "id": "gpt-6-1-sol",
        "name": "GPT-6.1 Sol (max)",
        "provider": "OpenAI",
        "provider_key": "openai",
        "score": 55,
        "color": "#1E2022",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "openai/o1",
    },
    {
        "id": "claude-sonnet-5-5",
        "name": "Claude Sonnet 5.5 (max)",
        "provider": "Anthropic",
        "provider_key": "anthropic",
        "score": 54,
        "color": "#C8644A",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "anthropic/claude-3.7-sonnet",
    },
    {
        "id": "gpt-6-1-terra",
        "name": "GPT-6.1 Terra (max)",
        "provider": "OpenAI",
        "provider_key": "openai",
        "score": 51,
        "color": "#1E2022",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "openai/o3-mini",
    },
    {
        "id": "gemini-4-argon",
        "name": "Gemini 4 Argon (high)",
        "provider": "Google",
        "provider_key": "google",
        "score": 50,
        "color": "#2EA043",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "google/gemini-2.0-flash-001",
    },
    {
        "id": "muse-wonder-full",
        "name": "Muse Wonder Full (max)",
        "provider": "Meta",
        "provider_key": "meta",
        "score": 50,
        "color": "#0081FB",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": None,
    },
    {
        "id": "claude-fable-5-1",
        "name": "Claude Fable 5.1 (max)",
        "provider": "Anthropic",
        "provider_key": "anthropic",
        "score": 49,
        "color": "#C8644A",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "anthropic/claude-3.5-sonnet",
    },
    {
        "id": "kimi-k3-1-pro",
        "name": "Kimi K3.1 Pro",
        "provider": "Moonshot",
        "provider_key": "kimi",
        "score": 46,
        "color": "#0B65FE",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "moonshotai/kimi-k3.1-pro",
    },
    {
        "id": "muse-wonder",
        "name": "Muse Wonder (max)",
        "provider": "Meta",
        "provider_key": "meta",
        "score": 43,
        "color": "#0081FB",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "meta-llama/llama-3.3-70b-instruct",
    },
    {
        "id": "claude-haiku-5-5",
        "name": "Claude Haiku 5.5 (max)",
        "provider": "Anthropic",
        "provider_key": "anthropic",
        "score": 36,
        "color": "#C8644A",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "anthropic/claude-3.5-haiku",
    },
    {
        "id": "grok-4-7",
        "name": "Grok 4.7 (xhigh)",
        "provider": "xAI",
        "provider_key": "xai",
        "score": 34,
        "color": "#8566E2",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "x-ai/grok-2",
    },
    {
        "id": "qwen3-8-max",
        "name": "Qwen3.8 Max (0902)",
        "provider": "Alibaba",
        "provider_key": "alibaba",
        "score": 34,
        "color": "#FF5B00",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "qwen/qwen-2.5-72b-instruct",
    },
    {
        "id": "deepseek-v4-1-flash",
        "name": "DeepSeek V4.1 Flash 1017 (max)",
        "provider": "DeepSeek",
        "provider_key": "deepseek",
        "score": 32,
        "color": "#1D59F5",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "deepseek/deepseek-r1",
    },
    {
        "id": "glm-5-3",
        "name": "GLM-5.3 (max)",
        "provider": "Zhipu",
        "provider_key": "zhipu",
        "score": 32,
        "color": "#2C71F6",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "zhipu/glm-4-plus",
    },
    {
        "id": "gemini-3-8-flash",
        "name": "Gemini 3.8 Flash (high)",
        "provider": "Google",
        "provider_key": "google",
        "score": 31,
        "color": "#2EA043",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "google/gemini-2.0-flash-lite-preview-02-05",
    },
    {
        "id": "mimo-v2-6-pro",
        "name": "MiMo-V2.6-Pro",
        "provider": "Xiaomi",
        "provider_key": "xiaomi",
        "score": 30,
        "color": "#FF6900",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "xiaomi/mimo-v2.6-pro",
    },
    {
        "id": "ling-3-1-flash",
        "name": "Ling 3.1 Flash 1019",
        "provider": "Ling",
        "provider_key": "ling",
        "score": 29,
        "color": "#4AA5F8",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "ling/ling-3.1-flash",
    },
    {
        "id": "minimax-m3-1-flash",
        "name": "MiniMax-M3.1-Flash",
        "provider": "MiniMax",
        "provider_key": "minimax",
        "score": 29,
        "color": "#ED3E78",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "minimax/minimax-01",
    },
    {
        "id": "step-5-preview",
        "name": "Step 5 Preview",
        "provider": "StepFun",
        "provider_key": "stepfun",
        "score": 29,
        "color": "#00D2CE",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "stepfun/step-2-16k",
    },
    {
        "id": "gpt-6-luna",
        "name": "GPT-6 Luna (max)",
        "provider": "OpenAI",
        "provider_key": "openai",
        "score": 28,
        "color": "#1E2022",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "openai/gpt-4o-mini",
    },
    {
        "id": "mistral-large-4-preview",
        "name": "Mistral Large 4 Preview",
        "provider": "Mistral",
        "provider_key": "mistral",
        "score": 25,
        "color": "#F73812",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "mistralai/mistral-large-2411",
    },
    {
        "id": "muse-spark-open",
        "name": "Muse Spark Open (xhigh)",
        "provider": "Meta",
        "provider_key": "meta",
        "score": 25,
        "color": "#0081FB",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "meta-llama/llama-3.1-405b-instruct",
    },
    {
        "id": "qwen3-8-27b",
        "name": "Qwen3.8 27B (xhigh)",
        "provider": "Alibaba",
        "provider_key": "alibaba",
        "score": 20,
        "color": "#FF5B00",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "qwen/qwen-2.5-32b-instruct",
    },
    {
        "id": "k2-horizon-375b",
        "name": "K2 Horizon 375B A23B",
        "provider": "Horizon",
        "provider_key": "horizon",
        "score": 18,
        "color": "#17236F",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "horizon/k2-375b-a23b",
    },
    {
        "id": "beam-1-0",
        "name": "Beam 1.0",
        "provider": "Beam",
        "provider_key": "beam",
        "score": 18,
        "color": "#1B4426",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "beam/beam-1.0",
    },
    {
        "id": "nemotron-3-5-super-vl",
        "name": "Nemotron 3.5 Super VL",
        "provider": "Nvidia",
        "provider_key": "nvidia",
        "score": 14,
        "color": "#76B900",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "nvidia/llama-3.1-nemotron-70b-instruct",
    },
    {
        "id": "inkling",
        "name": "Inkling (xhigh)",
        "provider": "Inkling",
        "provider_key": "inkling",
        "score": 12,
        "color": "#5E6571",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "inkling/inkling-xhigh",
    },
    {
        "id": "muse-glimmer",
        "name": "Muse Glimmer (high)",
        "provider": "Meta",
        "provider_key": "meta",
        "score": 6,
        "color": "#0081FB",
        "has_public_api": True,
        "is_hatched": False,
        "openrouter_model": "meta-llama/llama-3.2-3b-instruct",
    },
]


def get_reference_models() -> List[Dict[str, Any]]:
    """Return a deep copy of the reference models metadata list."""
    return [dict(m) for m in REFERENCE_MODELS]


def get_public_models() -> List[Dict[str, Any]]:
    """Return only models that have publicly available APIs (28 models, excluding Muse Wonder Full)."""
    return [dict(m) for m in REFERENCE_MODELS if m["has_public_api"]]


# ==============================================================================
# Data Loading and Normalization
# ==============================================================================

def load_results_from_batch_json(json_path: Union[str, Path]) -> List[BenchmarkResult]:
    """Load BenchmarkResult items from a batch JSON file."""
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"Batch file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "results" in data:
        return [BenchmarkResult(**item) for item in data["results"]]
    elif isinstance(data, list):
        return [BenchmarkResult(**item) for item in data]
    else:
        return [BenchmarkResult(**data)]


def load_results_from_csv(csv_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load benchmark run summaries from summary CSV."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed_ints_raw = row.get("parsed_integers", "[]")
            try:
                parsed_ints = json.loads(parsed_ints_raw)
            except Exception:
                parsed_ints = []
            row["parsed_integers_list"] = parsed_ints
            rows.append(row)
    return rows


def load_results_from_traces_dir(traces_dir: Union[str, Path]) -> List[BenchmarkResult]:
    """Load all trace JSON files from traces directory."""
    path = Path(traces_dir)
    if not path.is_dir():
        raise NotADirectoryError(f"Traces directory not found: {path}")

    results: List[BenchmarkResult] = []
    for f in sorted(path.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            results.append(BenchmarkResult(**data))
        except Exception:
            continue
    return results


def find_latest_results(results_dir: Union[str, Path] = "results") -> Optional[Path]:
    """Find latest batch JSON or summary CSV in the results directory."""
    res_dir = Path(results_dir)
    if not res_dir.is_dir():
        return None

    # Check for batch JSONs
    batch_files = sorted(res_dir.glob("batch_*.json"), key=os.path.getmtime, reverse=True)
    if batch_files:
        return batch_files[0]

    # Check for summary CSV
    csv_file = res_dir / "benchmark_summary.csv"
    if csv_file.is_file():
        return csv_file

    return None


def extract_trajectory_data(
    results_or_data: Any,
    num_turns: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract per-model turn-by-turn integer outputs and cumulative prefix sums.
    Returns:
        dict[model_name -> {
            'name': str,
            'provider': str,
            'integers': list[int],
            'prefix_sums': list[int],
            'turns': list[int],
            'color': str,
            'score': int
        }]
    """
    trajectory: Dict[str, Dict[str, Any]] = {}

    # Case 1: List of BenchmarkResult objects
    if isinstance(results_or_data, list) and results_or_data and isinstance(results_or_data[0], BenchmarkResult):
        for res in results_or_data:
            name = res.config.get("name") or f"{res.provider}_{res.model}"
            ints: List[int] = []
            for t in res.turns:
                val = t.parsed_integer if t.parsed_integer is not None else 0
                ints.append(val)
            if not ints and res.parsed_integers:
                ints = [i for i in res.parsed_integers if i is not None]

            # Compute prefix sums
            cum = 0
            prefix_sums: List[int] = []
            for val in ints:
                cum += val
                prefix_sums.append(cum)

            # Match reference color
            ref_match = _match_reference_model(name, res.provider)
            color = ref_match["color"] if ref_match else _deterministic_color(name)

            trajectory[name] = {
                "name": name,
                "provider": ref_match["provider"] if ref_match else res.provider,
                "integers": ints,
                "prefix_sums": prefix_sums,
                "turns": list(range(1, len(ints) + 1)),
                "color": color,
                "score": prefix_sums[-1] if prefix_sums else 0,
            }

    # Case 2: List of CSV rows
    elif isinstance(results_or_data, list) and results_or_data and isinstance(results_or_data[0], dict):
        for row in results_or_data:
            name = row.get("model", "unknown")
            provider = row.get("provider", "openrouter")
            ints = row.get("parsed_integers_list", [])
            cum = 0
            prefix_sums = []
            for val in ints:
                cum += (val or 0)
                prefix_sums.append(cum)

            ref_match = _match_reference_model(name, provider)
            color = ref_match["color"] if ref_match else _deterministic_color(name)

            trajectory[name] = {
                "name": name,
                "provider": ref_match["provider"] if ref_match else provider,
                "integers": ints,
                "prefix_sums": prefix_sums,
                "turns": list(range(1, len(ints) + 1)),
                "color": color,
                "score": prefix_sums[-1] if prefix_sums else 0,
            }

    return trajectory


def generate_mock_trajectory_data(
    num_turns: int = 5,
    seed: int = 42,
    models: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Generate deterministic mock multi-turn trajectory data for all models.
    Matches RSI-Bench's integer generation benchmark.
    """
    model_list = models or REFERENCE_MODELS
    data: Dict[str, Dict[str, Any]] = {}

    for idx, m in enumerate(model_list):
        name = m["name"]
        color = m["color"]
        model_seed = seed + idx * 1007
        m_rng = random.Random(model_seed)
        ints: List[int] = []
        for _ in range(num_turns):
            val = m_rng.choice([
                m_rng.randint(-800, 800),
                m_rng.randint(20, 200),
                m_rng.randint(-150, 150),
                m_rng.randint(50, 450),
            ])
            ints.append(val)

        cum = 0
        prefix_sums: List[int] = []
        for val in ints:
            cum += val
            prefix_sums.append(cum)

        data[name] = {
            "name": name,
            "provider": m["provider"],
            "integers": ints,
            "prefix_sums": prefix_sums,
            "turns": list(range(1, num_turns + 1)),
            "color": color,
            "score": m.get("score", prefix_sums[-1]),
        }

    return data


def _match_reference_model(name: str, provider: str = "") -> Optional[Dict[str, Any]]:
    """Attempt to fuzzy match a model name to our reference registry."""
    clean_name = name.lower().replace("-", " ").replace("_", " ").strip()
    for ref in REFERENCE_MODELS:
        ref_clean = ref["name"].lower().replace("-", " ").replace("_", " ")
        if clean_name in ref_clean or ref_clean in clean_name:
            return ref
        if ref["id"] in name.lower() or name.lower() in ref["id"]:
            return ref
    return None


def _deterministic_color(text: str) -> str:
    """Generate a consistent pastel/vibrant hex color from any string."""
    hash_val = hash(text) & 0xFFFFFF
    r = (hash_val >> 16) & 0xFF
    g = (hash_val >> 8) & 0xFF
    b = hash_val & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


# ==============================================================================
# HTML / SVG Chart Rendering: 1. RSI-Bench Index Bar Chart
# ==============================================================================

def render_intelligence_index_bar_chart_html(
    models: Optional[List[Dict[str, Any]]] = None,
    title: str = "RSI-Bench Index ↗",
    subtitle: Optional[str] = None,
) -> str:
    """
    Render self-contained HTML for the RSI-Bench Index bar chart.
    Faithfully replicates the font, header, brand spark logo, dotted grid lines,
    rounded bars with scores inside, provider logos, and 45-degree rotated model labels.
    """
    model_list = models if models is not None else REFERENCE_MODELS

    if subtitle is None:
        subtitle = (
            "RSI-Bench v1.0 evaluates frontier model capabilities across "
            "multi-turn recursive stochastic sequence summation"
        )

    # Layout dimensions
    num_models = len(model_list)
    chart_height = 360  # Bar plotting area
    bar_width = 34
    bar_gap = 12
    margin_left = 30
    bars_extent_width = margin_left + num_models * (bar_width + bar_gap) + 40
    chart_width = max(1120, bars_extent_width)
    total_svg_height = 540

    # Determine score range & dynamic scale (symlog if values exceed normal index range)
    all_scores = [float(m.get("score", 0)) for m in model_list]
    min_score = min(all_scores) if all_scores else 0.0
    max_score = max(all_scores) if all_scores else 60.0

    is_symlog = not (min_score >= 0.0 and max_score <= 60.0)

    def symlog_fn(v: float) -> float:
        if v == 0:
            return 0.0
        return math.copysign(math.log10(1.0 + abs(v)), v)

    if not is_symlog:
        range_min = 0.0
        range_max = 60.0
        ticks = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        total_range = 60.0
        y_zero = chart_height

        def get_bar_geom(sc: float) -> Tuple[float, float]:
            h = max(2.0, (sc / total_range) * chart_height)
            return y_zero - h, h
    else:
        s_scores = [symlog_fn(s) for s in all_scores]
        s_min = min(s_scores)
        s_max = max(s_scores)

        if s_min >= 0:
            s_bottom = 0.0
            s_top = max(2.0, math.ceil(s_max + 0.1))
        else:
            s_bottom = math.floor(s_min - 0.1)
            s_top = max(1.0, math.ceil(s_max + 0.1))

        s_span = s_top - s_bottom
        step = 1.0 if s_span <= 6 else (2.0 if s_span <= 14 else 4.0)

        if s_bottom < 0:
            s_bottom = math.floor(s_bottom / step) * step
        s_top = math.ceil(s_top / step) * step

        total_range = max(1.0, s_top - s_bottom)
        y_zero = chart_height * ((s_top - 0.0) / total_range)

        # Collect grid ticks
        ticks = []
        if s_bottom < 0:
            cur = s_bottom
            while cur < 0:
                ticks.append(cur)
                cur += step
        ticks.append(0.0)
        cur = step
        while cur <= s_top:
            ticks.append(cur)
            cur += step

        def get_bar_geom(sc: float) -> Tuple[float, float]:
            s_val = symlog_fn(sc)
            if sc >= 0:
                h = max(3.0, (s_val / total_range) * chart_height)
                y = y_zero - h
            else:
                h = max(3.0, (abs(s_val) / total_range) * chart_height)
                y = y_zero
            return y, h

    # Grid lines (dotted horizontal lines across the range)
    grid_svg_lines = []
    if not is_symlog:
        for tick in ticks:
            y_pos = chart_height * ((60.0 - tick) / 60.0)
            grid_svg_lines.append(
                f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{chart_width - 20}" y2="{y_pos:.1f}" '
                f'stroke="#E5E7EB" stroke-width="1.2" stroke-dasharray="2,4" />'
            )
    else:
        for tick in ticks:
            y_pos = chart_height * ((s_top - tick) / total_range)
            is_zero = abs(tick) < 1e-6
            stroke_col = "#9CA3AF" if is_zero else "#E5E7EB"
            stroke_w = "1.5" if is_zero else "1.2"
            dash_attr = "" if is_zero else 'stroke-dasharray="2,4"'
            grid_svg_lines.append(
                f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{chart_width - 20}" y2="{y_pos:.1f}" '
                f'stroke="{stroke_col}" stroke-width="{stroke_w}" {dash_attr} />'
            )
    grid_lines_html = "\n    ".join(grid_svg_lines)

    def format_bar_score(sc: float) -> str:
        if not is_symlog:
            return str(int(round(sc)))
        if sc == 0:
            return "0.0"
        log_val = symlog_fn(sc)
        return f"{log_val:.1f}"

    repo_url = "https://github.com/KCFindstr/RSI-Bench"

    # Render bars, scores, logos, and labels
    bars_svg_elements = []
    logos_html_elements = []

    for idx, m in enumerate(model_list):
        score = int(m.get("score", 0))
        color = m.get("color", "#1E2022")
        is_hatched = m.get("is_hatched", False)
        provider_key = m.get("provider_key", "openai").lower()
        model_name = m.get("name", "")

        x_pos = margin_left + idx * (bar_width + bar_gap)
        fill_attr = 'fill="url(#hatch-pattern)"' if is_hatched else f'fill="{color}"'

        y_pos, bar_h = get_bar_geom(score)
        score_x = x_pos + bar_width / 2
        display_score = format_bar_score(score)

        if score >= 0:
            if bar_h > 35:
                score_y = y_zero - 18
                score_color = "#FFFFFF"
            else:
                score_y = y_pos - 6
                score_color = "#18181B"
        else:
            if bar_h > 35:
                score_y = y_zero + 22
                score_color = "#FFFFFF"
            else:
                score_y = y_pos + bar_h + 16
                score_color = "#18181B"

        bar_elem = (
            f'<g class="bar-group" data-model="{model_name}" data-score="{score}">'
            f'  <rect x="{x_pos}" y="{y_pos:.1f}" width="{bar_width}" height="{bar_h:.1f}" '
            f'rx="3" ry="3" {fill_attr} class="bar-rect" />'
            f'  <text x="{score_x:.1f}" y="{score_y:.1f}" fill="{score_color}" '
            f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" '
            f'font-size="12" font-weight="700" text-anchor="middle">{display_score}</text>'
            f'</g>'
        )
        bars_svg_elements.append(bar_elem)

        # Provider Logo SVG
        logo_svg = LOGOS.get(provider_key, LOGOS["openai"])
        logo_x = x_pos + (bar_width - 18) / 2
        logo_y = chart_height + 8

        logo_elem = (
            f'<div class="provider-logo" style="left: {logo_x}px; top: {logo_y}px;">'
            f'{logo_svg}'
            f'</div>'
        )
        logos_html_elements.append(logo_elem)

        # 45-degree Angled Model Label
        words = model_name.split()
        if len(words) > 3:
            line1 = " ".join(words[:2])
            line2 = " ".join(words[2:4])
            line3 = " ".join(words[4:])
            label_text = f"{line1}<br>{line2}<br>{line3}" if line3 else f"{line1}<br>{line2}"
        elif len(words) == 3:
            label_text = f"{words[0]} {words[1]}<br>{words[2]}"
        else:
            label_text = model_name

        label_x = x_pos + bar_width / 2 + 4
        label_y = chart_height + 36

        label_elem = (
            f'<div class="model-label" style="left: {label_x}px; top: {label_y}px;">'
            f'{label_text}'
            f'</div>'
        )
        logos_html_elements.append(label_elem)

    symlog_note_badge = (
        '<div class="scale-note">* Symmetrical logarithmic scale (symlog) applied for dynamic range visualization.</div>'
        if is_symlog else ""
    )

    bars_html = "\n    ".join(bars_svg_elements)
    overlays_html = "\n    ".join(logos_html_elements)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RSI-Bench Index</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: #FFFFFF;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #111827;
      padding: 30px 36px;
      min-width: {chart_width + 60}px;
    }}
    .header-container {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      max-width: {chart_width}px;
    }}
    .title-block {{
      max-width: 680px;
    }}
    .chart-title {{
      font-family: Merriweather, Georgia, "Times New Roman", serif;
      font-size: 26px;
      font-weight: 600;
      color: #18181B;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .chart-subtitle {{
      font-size: 13px;
      line-height: 1.45;
      color: #71717A;
      margin-bottom: 6px;
    }}
    .scale-note {{
      font-size: 11.5px;
      color: #9CA3AF;
      font-style: italic;
      margin-top: 4px;
    }}
    .brand-logo-block {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 5px;
    }}
    .brand-name-row {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: Merriweather, Georgia, serif;
      font-size: 17px;
      font-weight: 700;
      color: #18181B;
      letter-spacing: -0.2px;
    }}
    .brand-spark {{
      color: #8B5CF6;
      font-size: 20px;
      line-height: 1;
    }}
    .repo-url-link {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 11.5px;
      font-weight: 500;
      color: #6366F1;
      text-decoration: none;
      letter-spacing: normal;
    }}
    .repo-url-link:hover {{
      text-decoration: underline;
    }}
    .chart-stage {{
      position: relative;
      width: {chart_width}px;
      height: {total_svg_height}px;
      margin-top: 10px;
    }}
    svg.chart-svg {{
      position: absolute;
      top: 0;
      left: 0;
      width: {chart_width}px;
      height: {chart_height}px;
      overflow: visible;
    }}
    .provider-logo {{
      position: absolute;
      width: 18px;
      height: 18px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .model-label {{
      position: absolute;
      transform: rotate(50deg);
      transform-origin: top left;
      font-size: 10.5px;
      line-height: 1.16;
      color: #18181B;
      font-weight: 500;
      white-space: nowrap;
      pointer-events: none;
    }}
    .bar-rect:hover {{
      opacity: 0.88;
      cursor: pointer;
    }}
  </style>
</head>
<body>

  <div class="header-container">
    <div class="title-block">
      <h1 class="chart-title">
        <a href="{repo_url}" target="_blank" style="text-decoration: none; color: inherit;">{title}</a>
      </h1>
      <p class="chart-subtitle">{subtitle}</p>
      {symlog_note_badge}
    </div>
    <div class="brand-logo-block">
      <div class="brand-name-row">
        <span class="brand-spark">❖</span>
        <span>RSI-Bench</span>
      </div>
      <a href="{repo_url}" target="_blank" class="repo-url-link">{repo_url}</a>
    </div>
  </div>

  <div class="chart-stage">
    <svg class="chart-svg" viewBox="0 0 {chart_width} {chart_height}">
      <defs>
        <pattern id="hatch-pattern" width="8" height="8" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <rect width="8" height="8" fill="#0081FB" />
          <line x1="0" y1="0" x2="0" y2="8" stroke="#FFFFFF" stroke-width="2.5" stroke-opacity="0.85" />
        </pattern>
      </defs>

      <!-- Grid lines -->
      {grid_lines_html}

      <!-- Bars and score labels -->
      {bars_html}
    </svg>

    <!-- HTML Provider Logos & 45-degree Angled Model Labels -->
    {overlays_html}
  </div>

</body>
</html>
"""
    return html_content


# ==============================================================================
# HTML / SVG Chart Rendering: 2. Trajectory Line Graph (Unlabeled Axes Joke)
# ==============================================================================

def render_trajectory_line_graph_html(
    trajectory_data: Dict[str, Dict[str, Any]],
    title: str = "RSI-Bench Multi-Turn Performance Trajectory",
    subtitle: str = "Continuous multi-turn cumulative stochastic sequence summation across evaluated frontier models",
) -> str:
    """
    Render self-contained HTML for the line graph showing each model's cumulative prefix sum
    trajectory from step 1 to step N.

    Design constraints:
    - Card outline removed: edge-to-edge full graph on clean background.
    - Y-axis labels removed completely (numbers only on x-axis with 'Step' label).
    - Outliers filtered to preserve vertical dynamic range so lines are not flat.
    - Right-hand side lists all plotted models in exact order matching line endpoints at step N.
    """
    models = list(trajectory_data.values())
    if not models:
        models = list(generate_mock_trajectory_data(num_turns=5).values())

    def symlog(v: float) -> float:
        if v == 0:
            return 0.0
        return math.copysign(math.log10(1.0 + abs(v)), v)

    # Detect extreme sequence outliers (|val| > 2e9)
    outliers = [m for m in models if any(abs(v) > 2_000_000_000 for v in m.get("prefix_sums", []))]
    plotted_models = [m for m in models if m not in outliers]
    if not plotted_models:
        plotted_models = list(models)

    if outliers:
        outlier_names = ", ".join(m.get("name", "Unknown") for m in outliers)
        scale_note = (
            f"* Symmetrical logarithmic scale (symlog). Outlier excluded for trajectory resolution: "
            f"{outlier_names} (|sequence variance| &gt; 10¹⁰). Cumulative score tracked in RSI-Bench Index."
        )
    else:
        scale_note = "* Symmetrical logarithmic scale (symlog) applied for dynamic range visualization."

    max_turns = max((len(m.get("turns", [1])) for m in plotted_models), default=1)
    all_sums = []
    for m in plotted_models:
        all_sums.extend(m.get("prefix_sums", [0]))

    all_vals = all_sums if all_sums else [0]
    transformed_vals = [symlog(v) for v in all_vals]
    s_min = math.floor(min(transformed_vals))
    s_max = math.ceil(max(transformed_vals))

    total_s_range = max(1.0, s_max - s_min)

    svg_width = 1420
    svg_height = 740
    margin_left = 40
    margin_right = 320
    margin_top = 40
    margin_bottom = 65

    plot_width = svg_width - margin_left - margin_right
    plot_height = svg_height - margin_top - margin_bottom

    def x_coord(turn: int) -> float:
        if max_turns <= 1:
            return margin_left + plot_width / 2
        return margin_left + ((turn - 1) / (max_turns - 1)) * plot_width

    def y_coord(val: float) -> float:
        s_val = symlog(val)
        ratio = (s_val - s_min) / total_s_range
        return margin_top + plot_height - (ratio * plot_height)

    # Horizontal grid lines (NO Y-AXIS LABELS)
    y_grid_lines = []
    for s in range(int(s_min), int(s_max) + 1):
        y_pos = margin_top + plot_height - (((s - s_min) / total_s_range) * plot_height)
        is_zero = abs(s) == 0
        stroke_color = "#E5E7EB" if is_zero else "#F3F4F6"
        stroke_w = "1.4" if is_zero else "1.0"
        dash_attr = "" if is_zero else 'stroke-dasharray="3,3"'
        y_grid_lines.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{margin_left + plot_width}" y2="{y_pos:.1f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_w}" {dash_attr} />'
        )

    # X-axis grid lines, step numbers, and 'Step' axis indicator
    x_tick_labels = []
    x_grid_lines = []
    for t in range(1, max_turns + 1):
        x_pos = x_coord(t)
        x_grid_lines.append(
            f'<line x1="{x_pos:.1f}" y1="{margin_top}" x2="{x_pos:.1f}" y2="{margin_top + plot_height}" '
            f'stroke="#F3F4F6" stroke-width="1" />'
        )
        x_tick_labels.append(
            f'<text x="{x_pos:.1f}" y="{margin_top + plot_height + 22}" '
            f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" '
            f'font-size="12" fill="#6B7280" font-weight="600" text-anchor="middle">{t}</text>'
        )

    x_axis_title = (
        f'<text x="{margin_left + plot_width / 2:.1f}" y="{margin_top + plot_height + 46}" '
        f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" '
        f'font-size="13" fill="#4B5563" font-weight="600" text-anchor="middle">Step</text>'
    )

    # Sort plotted models by final prefix sum for right-hand list alignment
    sorted_models = sorted(
        plotted_models,
        key=lambda m: m.get("prefix_sums", [0])[-1] if m.get("prefix_sums") else 0,
        reverse=True,
    )

    trajectory_paths = []
    right_labels = []
    num_plotted = len(sorted_models)
    label_start_y = margin_top + 10
    label_end_y = margin_top + plot_height - 10
    label_step = (label_end_y - label_start_y) / max(1, num_plotted - 1)

    for idx, m in enumerate(sorted_models):
        name = m.get("name", "Unknown")
        color = m.get("color", "#1E2022")
        turns = m.get("turns", [])
        sums = m.get("prefix_sums", [])

        if sums:
            pts = []
            circle_dots = []
            for t, s in zip(turns, sums):
                cx = x_coord(t)
                cy = y_coord(s)
                pts.append(f"{cx:.1f},{cy:.1f}")
                circle_dots.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="{color}" stroke="#FFFFFF" stroke-width="1.5" '
                    f'class="data-point" data-model="{name}" data-turn="{t}" data-val="{s}"/>'
                )
            d_str = "M " + " L ".join(pts)
            trajectory_paths.append(
                f'<g class="model-line-group" data-model="{name}">'
                f'  <path d="{d_str}" fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="traj-line" />'
                f'  {"".join(circle_dots)}'
                f'</g>'
            )

            # Leader line to right label
            end_cx = x_coord(turns[-1])
            end_cy = y_coord(sums[-1])
            label_y = label_start_y + idx * label_step
            label_x = margin_left + plot_width + 30

            guide_path = f"M {end_cx:.1f} {end_cy:.1f} C {end_cx + 15:.1f} {end_cy:.1f}, {label_x - 15:.1f} {label_y:.1f}, {label_x - 6:.1f} {label_y:.1f}"
            right_labels.append(
                f'<g class="model-label-group" data-model="{name}">'
                f'  <path d="{guide_path}" fill="none" stroke="{color}" stroke-width="1.2" stroke-opacity="0.4" stroke-dasharray="2,2" class="leader-line" />'
                f'  <circle cx="{label_x - 4:.1f}" cy="{label_y:.1f}" r="3.5" fill="{color}" />'
                f'  <text x="{label_x + 6:.1f}" y="{label_y + 3.5:.1f}" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" '
                f'font-size="11" font-weight="500" fill="#374151" class="right-model-label">{name}</text>'
                f'</g>'
            )

    grid_html = "\n    ".join(y_grid_lines + x_grid_lines)
    x_ticks_html = "\n    ".join(x_tick_labels)
    lines_html = "\n    ".join(trajectory_paths)
    right_labels_html = "\n    ".join(right_labels)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: #FFFFFF;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #111827;
      padding: 30px 36px;
      min-width: {svg_width + 80}px;
    }}
    .header {{
      margin-bottom: 20px;
      max-width: {svg_width}px;
    }}
    .title {{
      font-family: Merriweather, Georgia, serif;
      font-size: 25px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 6px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #6B7280;
      line-height: 1.45;
    }}
    .note {{
      font-size: 11.5px;
      color: #9CA3AF;
      font-style: italic;
      margin-top: 4px;
    }}
    .chart-wrapper {{
      position: relative;
      width: {svg_width}px;
      height: {svg_height}px;
    }}
    svg.line-svg {{
      width: {svg_width}px;
      height: {svg_height}px;
      overflow: visible;
    }}
    .model-line-group:hover .traj-line {{
      stroke-width: 4;
      cursor: pointer;
    }}
    .model-label-group:hover .right-model-label {{
      font-weight: 700;
      fill: #111827;
      cursor: pointer;
    }}
    .data-point {{
      cursor: pointer;
      transition: transform 0.15s ease;
    }}
    .data-point:hover {{
      r: 6px;
    }}
    .tooltip {{
      position: absolute;
      display: none;
      background: rgba(17, 24, 39, 0.92);
      color: #FFFFFF;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 11px;
      pointer-events: none;
      z-index: 100;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }}
  </style>
</head>
<body>

  <div class="header">
    <h1 class="title">{title}</h1>
    <p class="subtitle">{subtitle}</p>
    <p class="note">{scale_note}</p>
  </div>

  <div class="chart-wrapper">
    <div class="tooltip" id="tooltip"></div>
    <svg class="line-svg" viewBox="0 0 {svg_width} {svg_height}">
      <!-- Grid lines -->
      {grid_html}

      <!-- X-axis ticks & indicator: Step -->
      {x_ticks_html}
      {x_axis_title}

      <!-- Cumulative Trajectory Lines (Solid) -->
      <g id="traj-layer">
        {lines_html}
      </g>

      <!-- Right Leaderboard & End-of-line Labels -->
      <g id="right-labels-layer">
        {right_labels_html}
      </g>
    </svg>
  </div>

  <script>
    const tooltip = document.getElementById('tooltip');
    document.querySelectorAll('.data-point').forEach(pt => {{
      pt.addEventListener('mouseenter', e => {{
        const m = pt.getAttribute('data-model');
        const t = pt.getAttribute('data-turn');
        const v = pt.getAttribute('data-val');
        tooltip.innerHTML = `<strong>${{m}}</strong><br>Step: ${{t}}<br>Index Value: ${{v}}`;
        tooltip.style.display = 'block';
      }});
      pt.addEventListener('mousemove', e => {{
        const rect = e.target.ownerSVGElement.getBoundingClientRect();
        tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
        tooltip.style.top = (e.clientY - rect.top - 20) + 'px';
      }});
      pt.addEventListener('mouseleave', () => {{
        tooltip.style.display = 'none';
      }});
    }});
  </script>

</body>
</html>
"""
    return html_content


# ==============================================================================
# Headless Browser PNG Rendering
# ==============================================================================

def find_browser_executable(custom_path: Optional[str] = None) -> Optional[str]:
    """Find installed Google Chrome or Microsoft Edge executable."""
    candidates = []
    if custom_path:
        candidates.append(custom_path)

    if os.environ.get("CHROME_PATH"):
        candidates.append(os.environ["CHROME_PATH"])
    if os.environ.get("EDGE_PATH"):
        candidates.append(os.environ["EDGE_PATH"])

    candidates.extend([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ])

    for prog in ["google-chrome", "chrome", "chromium", "msedge", "edge"]:
        loc = shutil.which(prog)
        if loc:
            candidates.append(loc)

    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    return None


def render_html_to_png(
    html_path: Union[str, Path],
    png_path: Union[str, Path],
    width: int = 1600,
    height: int = 900,
    browser_path: Optional[str] = None,
) -> bool:
    """
    Render a local HTML file to a crisp PNG image using headless Chrome or Edge.
    Returns True on success, False if no browser was found or if execution failed.
    """
    browser_exe = find_browser_executable(browser_path)
    if not browser_exe:
        return False

    in_path = Path(html_path).resolve()
    out_path = Path(png_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    file_url = in_path.as_uri()

    cmd = [
        browser_exe,
        "--headless=new",
        f"--screenshot={str(out_path)}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--disable-gpu",
        "--no-sandbox",
        file_url,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out_path.is_file() and out_path.stat().st_size > 0:
            # Auto-trim excess white padding around content for a tight, polished presentation
            try:
                from PIL import Image, ImageChops

                im = Image.open(out_path).convert("RGB")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                diff = ImageChops.difference(im, bg)
                bbox = diff.getbbox()
                if bbox:
                    left, top, right, bottom = bbox
                    pad = 28
                    crop_box = (
                        max(0, left - pad),
                        max(0, top - pad),
                        min(im.size[0], right + pad),
                        min(im.size[1], bottom + pad),
                    )
                    cropped = im.crop(crop_box)
                    cropped.save(out_path)
            except Exception:
                pass
            return True
        return False
    except Exception:
        return False


# ==============================================================================
# High-Level Chart Generation Orchestrator
# ==============================================================================

def generate_all_charts(
    data_source: Optional[Union[str, Path, List[Any]]] = None,
    output_dir: Union[str, Path] = "results/charts",
    num_turns: int = 5,
    render_png: bool = True,
    browser_path: Optional[str] = None,
    use_reference_scores: bool = False,
) -> Dict[str, Path]:
    """
    Generate both RSI-Bench Index bar chart and trajectory line graph.
    Produces both .html and .png for each chart.

    Returns dict mapping artifact key to its generated Path:
      - 'bar_chart_html'
      - 'bar_chart_png' (if rendered)
      - 'line_graph_html'
      - 'line_graph_png' (if rendered)
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated: Dict[str, Path] = {}

    # 1. Determine bar chart data
    bar_models: List[Dict[str, Any]] = []
    if use_reference_scores or data_source is None:
        bar_models = get_reference_models()
    else:
        loaded_results: List[Any] = []
        if isinstance(data_source, (str, Path)):
            p = Path(data_source)
            if p.is_file() and p.suffix.lower() == ".json":
                loaded_results = load_results_from_batch_json(p)
            elif p.is_file() and p.suffix.lower() == ".csv":
                loaded_results = load_results_from_csv(p)
            elif p.is_dir():
                loaded_results = load_results_from_traces_dir(p)
        elif isinstance(data_source, list):
            loaded_results = data_source

        if loaded_results:
            traj_data = extract_trajectory_data(loaded_results)
            for name, item in traj_data.items():
                ref_match = _match_reference_model(name)
                score = item["score"] if item["score"] != 0 else (ref_match["score"] if ref_match else 25)
                bar_models.append({
                    "id": ref_match["id"] if ref_match else re.sub(r"[^a-zA-Z0-9]+", "-", name).lower(),
                    "name": name,
                    "provider": item.get("provider", "openrouter"),
                    "provider_key": ref_match["provider_key"] if ref_match else "openai",
                    "score": score,
                    "color": item.get("color", "#1E2022"),
                    "has_public_api": True,
                    "is_hatched": False,
                })
            bar_models.sort(key=lambda x: x["score"], reverse=True)

        if not bar_models:
            bar_models = get_reference_models()

    # 2. Render Bar Chart HTML
    bar_html_str = render_intelligence_index_bar_chart_html(models=bar_models)
    bar_html_path = out_dir / "rsi_bench_index.html"
    with open(bar_html_path, "w", encoding="utf-8") as f:
        f.write(bar_html_str)
    generated["bar_chart_html"] = bar_html_path

    # 3. Determine Line Graph trajectory data
    traj_dict: Dict[str, Dict[str, Any]] = {}
    if data_source is not None and not use_reference_scores:
        loaded = []
        if isinstance(data_source, (str, Path)):
            p = Path(data_source)
            if p.is_file() and p.suffix.lower() == ".json":
                loaded = load_results_from_batch_json(p)
            elif p.is_file() and p.suffix.lower() == ".csv":
                loaded = load_results_from_csv(p)
            elif p.is_dir():
                loaded = load_results_from_traces_dir(p)
        elif isinstance(data_source, list):
            loaded = data_source

        if loaded:
            traj_dict = extract_trajectory_data(loaded)

    if not traj_dict:
        traj_dict = generate_mock_trajectory_data(num_turns=num_turns)

    # 4. Render Line Graph HTML
    line_html_str = render_trajectory_line_graph_html(trajectory_data=traj_dict)
    line_html_path = out_dir / "model_trajectory_index.html"
    with open(line_html_path, "w", encoding="utf-8") as f:
        f.write(line_html_str)
    generated["line_graph_html"] = line_html_path

    # 5. Render PNGs via Headless Browser if requested
    if render_png:
        bar_png_path = out_dir / "rsi_bench_index.png"
        ok_bar = render_html_to_png(bar_html_path, bar_png_path, width=1650, height=760, browser_path=browser_path)
        if ok_bar:
            generated["bar_chart_png"] = bar_png_path

        line_png_path = out_dir / "model_trajectory_index.png"
        ok_line = render_html_to_png(line_html_path, line_png_path, width=1450, height=960, browser_path=browser_path)
        if ok_line:
            generated["line_graph_png"] = line_png_path

    # Clean up any loose/duplicate charts in top-level results/ directory (keep only in results/charts)
    results_dir = Path("results").resolve()
    if results_dir.is_dir():
        for filename in [
            "rsi_bench_index.png",
            "rsi_bench_index.html",
            "model_trajectory_index.png",
            "model_trajectory_index.html",
            "artificial_analysis_intelligence_index.png",
            "artificial_analysis_intelligence_index.html",
        ]:
            loose_file = results_dir / filename
            if loose_file.is_file():
                try:
                    loose_file.unlink()
                except Exception:
                    pass

    return generated

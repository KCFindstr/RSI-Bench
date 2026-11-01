"""
Visualization engine for RSI-Bench.

Generates:
1. Artificial Analysis Intelligence Index style bar charts matching the benchmark design.
2. Multi-turn trajectory line graphs showing turn-by-turn outputs and cumulative prefix sums
   WITHOUT labeled axes (preserving the joke).
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

# SVG Provider Logos (Clean, self-contained vector paths)
LOGOS: Dict[str, str] = {
    "anthropic": (
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="#18181B">'
        '<path d="M13.8 3.5h3.3L23.5 20.5h-3.3l-1.6-3.8h-6.1l-1.6 3.8H7.6L13.8 3.5zm3.1 9.4l-1.9-4.7-1.9 4.7h3.8zM0.5 20.5h3.3L10 3.5H6.7L0.5 20.5z"/>'
        '</svg>'
    ),
    "openai": (
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="#18181B">'
        '<path d="M22.28 10.45a5.9 5.9 0 0 0-.47-4.49 6.06 6.06 0 0 0-4.74-3.13 6.04 6.04 0 0 0-5.32 1.6 5.9 5.9 0 0 0-4.14-.37 6.04 6.04 0 0 0-4.4 3.57 6.08 6.08 0 0 0 .74 5.97 5.93 5.93 0 0 0 .48 4.49 6.05 6.05 0 0 0 4.73 3.13 6.08 6.08 0 0 0 5.33-1.6 5.9 5.9 0 0 0 4.14.37 6.05 6.05 0 0 0 4.4-3.57 6.08 6.08 0 0 0-.75-5.97zm-8.83 9.47a4.2 4.2 0 0 1-2.9-.66l.16-.09 4.8-2.77a.9.9 0 0 0 .45-.78v-6.78l2.03 1.17v5.62a4.23 4.23 0 0 1-4.54 4.3zm-8.23-3.9a4.2 4.2 0 0 1-.5-2.93l.16.1 4.8 2.77a.9.9 0 0 0 .9 0l5.87-3.39v2.35l-4.87 2.81a4.23 4.23 0 0 1-6.36-1.71zm-1.1-8.91a4.2 4.2 0 0 1 2.4-2.27v5.74a.9.9 0 0 0 .45.78l5.87 3.39-2.03 1.17-4.87-2.81a4.23 4.23 0 0 1-1.82-5.97v-.03zm14.28 2.37l-5.87-3.39 2.03-1.17 4.87 2.81a4.23 4.23 0 0 1 1.82 5.97v.03a4.2 4.2 0 0 1-2.4 2.27v-5.74a.9.9 0 0 0-.45-.78zm2.63 4.96a4.23 4.23 0 0 1-2.06 2.7l-.16-.1-4.8-2.77a.9.9 0 0 0-.9 0l-5.87 3.39v-2.35l4.87-2.81a4.23 4.23 0 0 1 6.36 1.71l2.56.23zm-10.42-3.86l2.39-1.38 2.39 1.38v2.76l-2.39 1.38-2.39-1.38V10.58z"/>'
        '</svg>'
    ),
    "google": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>'
        '<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>'
        '<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>'
        '<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>'
        '</svg>'
    ),
    "meta": (
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="#0081FB">'
        '<path d="M16.94 4.5c-2.47 0-4.6 1.61-5.18 3.82-.4-1.74-1.96-3.05-3.8-3.05-2.2 0-3.98 1.83-3.98 4.08 0 1.54.85 2.89 2.1 3.57l4.9 2.68c.27.15.59.23.92.23s.65-.08.92-.23l4.9-2.68c1.25-.68 2.1-2.03 2.1-3.57 0-2.25-1.78-4.08-3.98-4.08zm-9.04 6.38c-1.25 0-2.27-1.04-2.27-2.3 0-1.28 1.02-2.31 2.27-2.31 1.15 0 2.11.86 2.25 1.99l-2.25 2.62zm8.16 0l-2.25-2.62c.14-1.13 1.1-1.99 2.25-1.99 1.25 0 2.27 1.03 2.27 2.31 0 1.26-1.02 2.3-2.27 2.3z"/>'
        '</svg>'
    ),
    "kimi": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#000000"/>'
        '<text x="6" y="17" font-family="Arial, sans-serif" font-weight="900" font-size="16" fill="#FFFFFF">K</text>'
        '</svg>'
    ),
    "xai": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#000000"/>'
        '<path fill="#FFFFFF" d="M14.2 10.7L20.4 3.5h-1.5L13.5 9.7 9.2 3.5H4.1l6.5 9.5L4.1 20.5h1.5l5.7-6.5 4.5 6.5h5.1l-6.7-9.8zm-2 2.3l-.7-1-5.3-7.6h2.3l4.3 6.1.7 1 5.6 7.9h-2.3l-4.6-6.4z"/>'
        '</svg>'
    ),
    "alibaba": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#FF5B00"/>'
        '<circle cx="12" cy="12" r="6" fill="#FFFFFF"/>'
        '<circle cx="12" cy="12" r="3" fill="#FF5B00"/>'
        '</svg>'
    ),
    "deepseek": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#1D59F5"/>'
        '<path fill="#FFFFFF" d="M12 5c-3.9 0-7 2.2-7 5 0 1.8 1.3 3.3 3.3 4.2L7 17l3.2-1.6c.6.1 1.2.2 1.8.2 3.9 0 7-2.2 7-5s-3.1-5-7-5z"/>'
        '</svg>'
    ),
    "zhipu": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#2C71F6"/>'
        '<text x="7" y="17" font-family="Arial, sans-serif" font-weight="900" font-size="16" fill="#FFFFFF">Z</text>'
        '</svg>'
    ),
    "xiaomi": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="5" fill="#FF6900"/>'
        '<path fill="#FFFFFF" d="M7 8h3v5h2V8h3v8h-3v-3h-2v3H7V8z"/>'
        '</svg>'
    ),
    "ling": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#18181B"/>'
        '<path fill="#4AA5F8" d="M12 4l5 8-5 8-5-8z"/>'
        '</svg>'
    ),
    "minimax": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#ED3E78"/>'
        '<path fill="#FFFFFF" d="M6 14V10h2v4H6zm3 2V8h2v8H9zm3 2V6h2v12h-2zm3-2V8h2v8h-2zm3-2V10h2v4h-2z"/>'
        '</svg>'
    ),
    "stepfun": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<circle cx="12" cy="12" r="10" fill="#00D2CE"/>'
        '<path fill="#FFFFFF" d="M8 16h8v-2h-3v-2h-2v-2H8v6z"/>'
        '</svg>'
    ),
    "mistral": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#F73812"/>'
        '<rect x="5.5" y="6" width="3.5" height="12" fill="#FFFFFF"/>'
        '<rect x="10.25" y="9.5" width="3.5" height="4" fill="#FFFFFF"/>'
        '<rect x="15" y="6" width="3.5" height="12" fill="#FFFFFF"/>'
        '</svg>'
    ),
    "horizon": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#17236F"/>'
        '<rect x="5.5" y="5.5" width="6" height="6" fill="#FFFFFF"/>'
        '<rect x="12.5" y="5.5" width="6" height="6" fill="#5070FF"/>'
        '<rect x="5.5" y="12.5" width="6" height="6" fill="#5070FF"/>'
        '<rect x="12.5" y="12.5" width="6" height="6" fill="#FFFFFF"/>'
        '</svg>'
    ),
    "beam": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#1B4426"/>'
        '<circle cx="12" cy="12" r="6" stroke="#FFFFFF" stroke-width="2" fill="none"/>'
        '<circle cx="12" cy="12" r="2" fill="#FFFFFF"/>'
        '</svg>'
    ),
    "nvidia": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#76B900"/>'
        '<path fill="#FFFFFF" d="M12.3 5.5c-3.6 0-6.6 2.5-7.5 5.9 1-.6 2.3-.9 3.6-.9 3 0 5.4 2.1 5.4 4.7 0 1.2-.5 2.3-1.4 3.1 3-.7 5.2-3.3 5.2-6.5 0-3.5-2.4-6.3-5.3-6.3zm-.2 2.2c1.9 0 3.4 1.8 3.4 4.1s-1.5 4.1-3.4 4.1c-.8 0-1.6-.3-2.1-.9.7-.7 1.1-1.7 1.1-2.7 0-1.8-1.5-3.3-3.4-3.5.7-.7 1.6-1.1 2.6-1.1z"/>'
        '</svg>'
    ),
    "inkling": (
        '<svg viewBox="0 0 24 24" width="18" height="18">'
        '<rect width="24" height="24" rx="4" fill="#5E6571"/>'
        '<circle cx="12" cy="12" r="6" fill="#FFFFFF"/>'
        '<path fill="#5E6571" d="M12 8l3 5H9z"/>'
        '</svg>'
    ),
}


REFERENCE_MODELS: List[Dict[str, Any]] = [
    {
        "id": "claude-opus-5-5",
        "name": "Claude Opus 5.5 (max with fallback)",
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
        "name": "Claude Sonnet 5.5 (max with fallback)",
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
        "has_public_api": False,  # Hatched: "No publicly available API"
        "is_hatched": True,
        "openrouter_model": None,
    },
    {
        "id": "claude-fable-5-1",
        "name": "Claude Fable 5.1 (max with fallback)",
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
# HTML / SVG Chart Rendering: 1. Artificial Analysis Intelligence Index
# ==============================================================================

def render_intelligence_index_bar_chart_html(
    models: Optional[List[Dict[str, Any]]] = None,
    title: str = "Artificial Analysis Intelligence Index ↗",
    subtitle: Optional[str] = None,
) -> str:
    """
    Render self-contained HTML for the Artificial Analysis Intelligence Index bar chart.
    Faithfully replicates the font, header, purple spark logo, dotted grid lines,
    rounded bars with scores inside, provider logos, and 45-degree rotated model labels.
    """
    model_list = models if models is not None else REFERENCE_MODELS

    if subtitle is None:
        subtitle = (
            "Artificial Analysis Intelligence Index v5.0 incorporates 9 evaluations: "
            "AA-Briefcase v1.1, AutomationBench-AA, Terminal-Bench 4.0, FrontierCode 2.0, "
            "AA-Omniscience v1.1, GDP.pdf, HLE-Diamond, CritPt v2 (Hard Subset), and "
            "Terminal-Bench-Science 0.1"
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

    # Determine score range & dynamic scale
    all_scores = [float(m.get("score", 0)) for m in model_list]
    min_score = min(all_scores) if all_scores else 0.0
    max_score = max(all_scores) if all_scores else 60.0

    if min_score >= 0.0 and max_score <= 60.0:
        range_min = 0.0
        range_max = 60.0
        ticks = [10, 20, 30, 40, 50, 60]
    else:
        val_min = min(0.0, min_score)
        val_max = max(60.0, max_score)
        span = val_max - val_min
        raw_step = max(1.0, span / 6)
        step_magnitude = 10 ** math.floor(math.log10(raw_step))
        normalized = raw_step / step_magnitude
        if normalized <= 1.0:
            nice_step = 1.0 * step_magnitude
        elif normalized <= 2.0:
            nice_step = 2.0 * step_magnitude
        elif normalized <= 5.0:
            nice_step = 5.0 * step_magnitude
        else:
            nice_step = 10.0 * step_magnitude

        range_min = math.floor(val_min / nice_step) * nice_step
        range_max = math.ceil(val_max / nice_step) * nice_step
        ticks = []
        cur = range_min
        while cur <= range_max + nice_step * 0.1:
            ticks.append(int(round(cur)) if nice_step >= 1 else round(cur, 2))
            cur += nice_step

    total_range = max(1.0, range_max - range_min)
    y_zero = chart_height * (range_max / total_range)

    # Grid lines (dotted horizontal lines across the range)
    grid_svg_lines = []
    for tick in ticks:
        if abs(tick) < 1e-6 and range_min < 0:
            continue
        y_pos = chart_height * ((range_max - tick) / total_range)
        grid_svg_lines.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{chart_width - 20}" y2="{y_pos:.1f}" '
            f'stroke="#E5E7EB" stroke-width="1.2" stroke-dasharray="2,4" />'
        )
    if range_min < 0:
        grid_svg_lines.append(
            f'<line x1="{margin_left}" y1="{y_zero:.1f}" x2="{chart_width - 20}" y2="{y_zero:.1f}" '
            f'stroke="#9CA3AF" stroke-width="1.5" />'
        )
    grid_lines_html = "\n    ".join(grid_svg_lines)

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

        if score >= 0:
            bar_h = max(2.0, (score / total_range) * chart_height)
            y_pos = y_zero - bar_h
            score_x = x_pos + bar_width / 2
            if bar_h > 35:
                score_y = y_zero - 18
                score_color = "#FFFFFF"
            else:
                score_y = y_pos - 6
                score_color = "#18181B"
        else:
            bar_h = max(2.0, (abs(score) / total_range) * chart_height)
            y_pos = y_zero
            score_x = x_pos + bar_width / 2
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
            f'font-size="13" font-weight="700" text-anchor="middle">{score}</text>'
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

    bars_html = "\n    ".join(bars_svg_elements)
    overlays_html = "\n    ".join(logos_html_elements)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Artificial Analysis Intelligence Index</title>
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
      margin-bottom: 14px;
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      color: #27272A;
      margin-top: 8px;
    }}
    .hatch-sample {{
      width: 18px;
      height: 18px;
      border: 1px solid #D1D5DB;
      border-radius: 2px;
      background: repeating-linear-gradient(
        45deg,
        #D1D5DB,
        #D1D5DB 2px,
        #FFFFFF 2px,
        #FFFFFF 5px
      );
    }}
    .brand-logo-block {{
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
      <h1 class="chart-title">{title}</h1>
      <p class="chart-subtitle">{subtitle}</p>
      <div class="legend-row">
        <div class="hatch-sample"></div>
        <span>No publicly available API</span>
      </div>
    </div>
    <div class="brand-logo-block">
      <span class="brand-spark">❖</span>
      <span>Artificial Analysis</span>
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
    title: str = "Multi-Turn Dynamic Performance Trajectory Index",
    subtitle: str = "Continuous multi-turn state convergence across evaluated frontier models",
) -> str:
    """
    Render self-contained HTML for the line graph showing each model's turn-by-turn output
    and cumulative prefix sum from turn 1 to turn N.

    CRITICAL JOKE CONSTRAINT:
    Axes are completely UNLABELED. No titles like "Turns", "Steps", "Score", "Integer",
    or "Prefix Sum" exist anywhere on the axes or graph frame.
    """
    models = list(trajectory_data.values())
    if not models:
        models = list(generate_mock_trajectory_data(num_turns=5).values())

    max_turns = max(len(m.get("turns", [1])) for m in models)
    all_sums = []
    all_raws = []
    for m in models:
        all_sums.extend(m.get("prefix_sums", [0]))
        all_raws.extend(m.get("integers", [0]))

    min_val = min(all_sums + all_raws) if (all_sums or all_raws) else -100
    max_val = max(all_sums + all_raws) if (all_sums or all_raws) else 100

    val_range = max(1, max_val - min_val)
    y_min = math.floor((min_val - 0.1 * val_range) / 100) * 100
    y_max = math.ceil((max_val + 0.1 * val_range) / 100) * 100
    total_y_range = max(1, y_max - y_min)

    svg_width = 1260
    svg_height = 540
    margin_left = 75
    margin_right = 35
    margin_top = 35
    margin_bottom = 45

    plot_width = svg_width - margin_left - margin_right
    plot_height = svg_height - margin_top - margin_bottom

    def x_coord(turn: int) -> float:
        if max_turns <= 1:
            return margin_left + plot_width / 2
        return margin_left + ((turn - 1) / (max_turns - 1)) * plot_width

    def y_coord(val: float) -> float:
        ratio = (val - y_min) / total_y_range
        return margin_top + plot_height - (ratio * plot_height)

    # Generate Y grid lines and unlabeled ticks (NUMBERS ONLY, NO AXIS LABEL)
    y_ticks_count = 8
    y_step = total_y_range / y_ticks_count
    y_grid_lines = []
    y_tick_labels = []

    for i in range(y_ticks_count + 1):
        v = y_min + i * y_step
        rounded_v = int(round(v / 50) * 50)
        y_pos = y_coord(rounded_v)
        y_grid_lines.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{margin_left + plot_width}" y2="{y_pos:.1f}" '
            f'stroke="#F3F4F6" stroke-width="1.2" stroke-dasharray="3,3" />'
        )
        y_tick_labels.append(
            f'<text x="{margin_left - 12}" y="{y_pos + 4:.1f}" font-family="-apple-system, sans-serif" '
            f'font-size="11" fill="#9CA3AF" text-anchor="end">{rounded_v}</text>'
        )

    # Generate X grid lines and unlabeled ticks (NUMBERS ONLY, NO AXIS LABEL)
    x_tick_labels = []
    x_grid_lines = []
    for t in range(1, max_turns + 1):
        x_pos = x_coord(t)
        x_grid_lines.append(
            f'<line x1="{x_pos:.1f}" y1="{margin_top}" x2="{x_pos:.1f}" y2="{margin_top + plot_height}" '
            f'stroke="#F9FAFB" stroke-width="1" />'
        )
        x_tick_labels.append(
            f'<text x="{x_pos:.1f}" y="{margin_top + plot_height + 22}" font-family="-apple-system, sans-serif" '
            f'font-size="12" fill="#6B7280" font-weight="600" text-anchor="middle">{t}</text>'
        )

    zero_line_svg = ""
    if y_min <= 0 <= y_max:
        z_y = y_coord(0)
        zero_line_svg = (
            f'<line x1="{margin_left}" y1="{z_y:.1f}" x2="{margin_left + plot_width}" y2="{z_y:.1f}" '
            f'stroke="#D1D5DB" stroke-width="1.5" />'
        )

    trajectory_paths = []
    raw_output_paths = []
    legend_items = []

    for m in models:
        name = m.get("name", "Unknown")
        color = m.get("color", "#1E2022")
        turns = m.get("turns", [])
        sums = m.get("prefix_sums", [])
        raws = m.get("integers", [])

        # Prefix sum points (Cumulative trajectory)
        if sums:
            pts = []
            circle_dots = []
            for t, s, r in zip(turns, sums, raws):
                cx = x_coord(t)
                cy = y_coord(s)
                pts.append(f"{cx:.1f},{cy:.1f}")
                circle_dots.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{color}" stroke="#FFFFFF" stroke-width="1.5" '
                    f'class="data-point" data-model="{name}" data-turn="{t}" data-val="{s}" data-raw="{r}"/>'
                )
            d_str = "M " + " L ".join(pts)
            trajectory_paths.append(
                f'<g class="model-line-group" data-model="{name}">'
                f'  <path d="{d_str}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="traj-line" />'
                f'  {"".join(circle_dots)}'
                f'</g>'
            )

        # Raw turn-by-turn outputs (Dashed line)
        if raws:
            raw_pts = []
            raw_dots = []
            for t, r in zip(turns, raws):
                cx = x_coord(t)
                cy = y_coord(r)
                raw_pts.append(f"{cx:.1f},{cy:.1f}")
                raw_dots.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="{color}" opacity="0.75" />'
                )
            raw_d = "M " + " L ".join(raw_pts)
            raw_output_paths.append(
                f'<g class="raw-output-group" data-model="{name}">'
                f'  <path d="{raw_d}" fill="none" stroke="{color}" stroke-width="1.2" stroke-dasharray="3,3" opacity="0.65" />'
                f'  {"".join(raw_dots)}'
                f'</g>'
            )

        legend_items.append(
            f'<div class="legend-pill" data-model="{name}">'
            f'  <span class="legend-color-dot" style="background-color: {color};"></span>'
            f'  <span class="legend-name" title="{name}">{name}</span>'
            f'</div>'
        )

    grid_html = "\n    ".join(y_grid_lines + x_grid_lines)
    y_ticks_html = "\n    ".join(y_tick_labels)
    x_ticks_html = "\n    ".join(x_tick_labels)
    lines_html = "\n    ".join(trajectory_paths)
    raw_lines_html = "\n    ".join(raw_output_paths)
    legend_html = "\n    ".join(legend_items)

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
      background-color: #FAFAFA;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #111827;
      padding: 28px 36px;
    }}
    .container {{
      max-width: 1380px;
      margin: 0 auto;
      background: #FFFFFF;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      padding: 28px 32px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      border-bottom: 1px solid #F3F4F6;
      padding-bottom: 16px;
    }}
    .title-block {{
      max-width: 800px;
    }}
    .title {{
      font-family: Merriweather, Georgia, serif;
      font-size: 23px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 6px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #6B7280;
      line-height: 1.5;
    }}
    .controls {{
      display: flex;
      gap: 6px;
      background: #F3F4F6;
      padding: 4px;
      border-radius: 8px;
    }}
    .ctrl-btn {{
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      border: none;
      background: transparent;
      color: #4B5563;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .ctrl-btn.active {{
      background: #FFFFFF;
      color: #111827;
      box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }}
    .header-actions {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }}
    .series-legend {{
      display: flex;
      align-items: center;
      gap: 14px;
      font-size: 11.5px;
      color: #4B5563;
      font-weight: 500;
    }}
    .series-badge {{
      display: flex;
      align-items: center;
      gap: 5px;
    }}
    .chart-wrapper {{
      position: relative;
      width: {svg_width}px;
      height: {svg_height}px;
      margin: 0 auto;
    }}
    svg.line-svg {{
      width: {svg_width}px;
      height: {svg_height}px;
      overflow: visible;
    }}
    .legend-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px 14px;
      margin-top: 24px;
      border-top: 1px solid #F3F4F6;
      padding-top: 18px;
    }}
    .legend-pill {{
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 11.5px;
      color: #374151;
      padding: 3px 6px;
      border-radius: 4px;
      cursor: pointer;
      transition: background-color 0.1s ease;
    }}
    .legend-pill:hover {{
      background-color: #F9FAFB;
    }}
    .legend-color-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
    .legend-name {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
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

  <div class="container">
    <div class="header">
      <div class="title-block">
        <h1 class="title">{title}</h1>
        <p class="subtitle">{subtitle}</p>
      </div>
      <div class="header-actions">
        <div class="controls">
          <button class="ctrl-btn active" id="btn-combined" onclick="setMode('combined')">Combined View</button>
          <button class="ctrl-btn" id="btn-traj" onclick="setMode('traj')">Trajectory Curve</button>
          <button class="ctrl-btn" id="btn-raw" onclick="setMode('raw')">Output Series</button>
        </div>
        <div class="series-legend">
          <span class="series-badge">
            <svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="#374151" stroke-width="2.5" stroke-linecap="round"/></svg>
            Trajectory Curve
          </span>
          <span class="series-badge">
            <svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="#6B7280" stroke-width="1.5" stroke-dasharray="3,3"/></svg>
            Output Series
          </span>
        </div>
      </div>
    </div>

    <div class="chart-wrapper">
      <div class="tooltip" id="tooltip"></div>
      <svg class="line-svg" viewBox="0 0 {svg_width} {svg_height}">
        <!-- Grid lines -->
        {grid_html}
        {zero_line_svg}

        <!-- Axes ticks: Numbers only! NO Axis Titles -->
        {y_ticks_html}
        {x_ticks_html}

        <!-- Raw Turn Output Lines (Dashed) - Visible by default in Combined View -->
        <g id="raw-layer">
          {raw_lines_html}
        </g>

        <!-- Cumulative Trajectory Lines (Solid) -->
        <g id="traj-layer">
          {lines_html}
        </g>
      </svg>
    </div>

    <div class="legend-grid">
      {legend_html}
    </div>
  </div>

  <script>
    function setMode(mode) {{
      const trajLayer = document.getElementById('traj-layer');
      const rawLayer = document.getElementById('raw-layer');
      const btnTraj = document.getElementById('btn-traj');
      const btnRaw = document.getElementById('btn-raw');
      const btnCombined = document.getElementById('btn-combined');

      btnTraj.classList.remove('active');
      btnRaw.classList.remove('active');
      btnCombined.classList.remove('active');

      if (mode === 'traj') {{
        trajLayer.style.display = 'block';
        rawLayer.style.display = 'none';
        btnTraj.classList.add('active');
      }} else if (mode === 'raw') {{
        trajLayer.style.display = 'none';
        rawLayer.style.display = 'block';
        btnRaw.classList.add('active');
      }} else if (mode === 'combined') {{
        trajLayer.style.display = 'block';
        rawLayer.style.display = 'block';
        btnCombined.classList.add('active');
      }}
    }}

    const tooltip = document.getElementById('tooltip');
    document.querySelectorAll('.data-point').forEach(pt => {{
      pt.addEventListener('mouseenter', e => {{
        const m = pt.getAttribute('data-model');
        const t = pt.getAttribute('data-turn');
        const v = pt.getAttribute('data-val');
        const r = pt.getAttribute('data-raw');
        tooltip.innerHTML = `<strong>${{m}}</strong><br>Position: ${{t}}<br>Index Value: ${{v}}<br>Turn Delta: ${{r}}`;
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
        return out_path.is_file() and out_path.stat().st_size > 0
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
    Generate both Artificial Analysis bar chart and trajectory line graph.
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
    bar_html_path = out_dir / "artificial_analysis_intelligence_index.html"
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
        bar_png_path = out_dir / "artificial_analysis_intelligence_index.png"
        ok_bar = render_html_to_png(bar_html_path, bar_png_path, width=1650, height=760, browser_path=browser_path)
        if ok_bar:
            generated["bar_chart_png"] = bar_png_path

        line_png_path = out_dir / "model_trajectory_index.png"
        ok_line = render_html_to_png(line_html_path, line_png_path, width=1450, height=960, browser_path=browser_path)
        if ok_line:
            generated["line_graph_png"] = line_png_path

    return generated

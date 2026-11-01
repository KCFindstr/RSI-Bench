# RSI-Bench: Multi-Turn LLM Benchmark Suite

A multi-turn Large Language Model (LLM) benchmark suite designed for evaluating integer generation consistency, prompt caching efficiency, and thinking/reasoning trace capture across all major AI providers.

## Key Features

- **Multi-Turn Protocol**: Executes conversational turns requesting:
  > *"Generate a random integer. Do NOT output anything else."*
  Preserves full multi-turn dialogue history across turns to measure context retention and prompt caching.
- **Comprehensive Provider Support**:
  - **Google Gemini Interactions API**: Unified agent/model interface (`/v1beta/interactions`) with `previous_interaction_id` state tracking, reasoning/thought extraction from `steps`/`outputs`, and context caching.
  - **Google Gemini Content API**: Standard `generateContent` endpoint with `thinkingConfig` and `cachedContentTokenCount`.
  - **Anthropic Claude**: Messages API (`/v1/messages`) with prompt caching (`cache_control: {"type": "ephemeral"}`) and extended thinking blocks.
  - **OpenAI Responses API**: Modern `/v1/responses` route with multi-turn items and reasoning configuration.
  - **OpenAI Chat Completions**: Regular `/v1/chat/completions` route supporting `reasoning_effort` (o1, o3-mini) and `prompt_tokens_details.cached_tokens`.
  - **OpenAI Text Completions**: Legacy/raw text completions route (`/v1/completions`) for direct text generation.
  - **DeepSeek**: Native reasoning extraction (`reasoning_content`) and prompt cache hit metrics (`prompt_cache_hit_tokens`).
  - **OpenRouter**: Unified model router with reasoning capture and provider routing options.
  - **Groq**: Ultra-fast inference with reasoning model support (DeepSeek R1 distill).
  - **Mistral AI**: Standard chat completions.
  - **Together AI**: Open-source inference with reasoning support.
  - **Cohere**: V2 chat completions (`/v2/chat`).
  - **Generic OpenAI-Compatible**: Connects to local servers (Ollama, vLLM, LMStudio, LocalAI) or custom proxies.
  - **Mock Provider**: Deterministic offline simulation for testing and CI/CD without API keys.
- **Thinking & Trace Preservation**:
  - Natively extracts structured reasoning/thinking fields from provider APIs.
  - Automatically isolates inline `<think>...</think>` and `<thought>...</thought>` tags.
  - Saves full raw request and response payloads, latency breakdown, and token usage.
- **Prompt Caching Tracking**:
  - Automatically activates provider prompt caching headers/flags (Anthropic ephemeral breakpoints, Gemini context cache, OpenAI/DeepSeek prefix caching).
  - Logs cached token metrics across all turns.
- **Robust Output Parser**:
  - Strips thinking tags, markdown wrappers (`**int**`, `` `int` ``, ```` ```int``` ````), prefixes (`Output: 42`), trailing punctuation, and conversational artifacts.
  - Handles comma-formatted integers (`1,000`), Unicode minus (`−42`), LaTeX math (`\boxed{42}`, `$$42$$`), and JSON outputs (`{"integer": 42}`).
  - Validates and stores the extracted integer.
- **Structured Storage**:
  - Full trace JSON files (`results/traces/<provider>_<model>_<run_id>.json`).
  - Human-readable Markdown run reports (`results/traces/<provider>_<model>_<run_id>.md`).
  - Centralized CSV log for cross-model benchmarking (`results/benchmark_summary.csv`).

---

## Directory Structure

```
RSI-Bench/
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
├── run.cmd                    # Windows quick launcher
├── run_benchmark.py           # Quick CLI runner script
├── config.example.yaml        # Tracked template configuration (YAML)
├── config.example.json        # Tracked template configuration (JSON)
├── config.yaml                # Gitignored local multi-run configuration
├── rsi_bench/
│   ├── __init__.py
│   ├── cli.py                 # Command-line interface and argument handling
│   ├── models.py              # Pydantic data models (TurnTrace, BenchmarkResult, etc.)
│   ├── config.py              # Provider registries, default models, and env key lookup
│   ├── parser.py              # Integer parsing and thinking tag extraction
│   ├── cache.py               # Local response caching layer (disk-backed)
│   ├── runner.py              # Multi-turn benchmark orchestration engine
│   ├── storage.py             # Trace, Markdown, and CSV result serialization
│   ├── utils/
│   │   ├── __init__.py
│   │   └── formatting.py      # Terminal formatting, tables, and colorized outputs
│   └── providers/
│       ├── __init__.py        # Provider factory and registry
│       ├── base.py            # BaseProvider abstract class with retries
│       ├── anthropic.py       # Anthropic Messages provider
│       ├── gemini_interactions.py # Google Gemini Interactions API provider
│       ├── gemini.py          # Google Gemini Content API (generateContent) provider
│       ├── openai_chat.py     # OpenAI Chat Completions provider
│       ├── openai_completion.py # OpenAI Text Completions provider
│       ├── openai_responses.py# OpenAI Responses API provider
│       ├── deepseek.py        # DeepSeek API provider
│       ├── openrouter.py      # OpenRouter provider
│       ├── groq.py            # Groq provider
│       ├── mistral.py         # Mistral provider
│       ├── together.py        # Together AI provider
│       ├── cohere.py          # Cohere V2 provider
│       └── generic_openai.py  # Generic OpenAI-compatible / Ollama provider
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parser.py         # Integer parsing and thinking extraction tests
    ├── test_cache.py          # Persistent cache tests
    ├── test_models.py         # Model serialization and token addition tests
    ├── test_providers.py      # Mock HTTP transport tests for all providers
    ├── test_runner.py         # Multi-turn benchmark orchestration tests
    ├── test_storage.py        # Result export tests
    └── test_cli.py            # CLI integration tests
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd RSI-Bench

# Install dependencies
pip install -r requirements.txt
```

---

## Environment Variables

Set the API keys for the providers you wish to benchmark:

| Provider | Environment Variable | Default Model | Route / Endpoint |
| :--- | :--- | :--- | :--- |
| **Google Gemini Interactions** | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `gemini-2.5-flash` | `POST /v1beta/interactions` |
| **Google Gemini Content** | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `gemini-2.5-flash` | `POST /v1beta/models/...:generateContent` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-3-7-sonnet-20250219` | `POST /v1/messages` |
| **OpenAI Responses** | `OPENAI_API_KEY` | `gpt-4o` | `POST /v1/responses` |
| **OpenAI Chat** | `OPENAI_API_KEY` | `gpt-4o` | `POST /v1/chat/completions` |
| **OpenAI Completion** | `OPENAI_API_KEY` | `gpt-3.5-turbo-instruct` | `POST /v1/completions` |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-reasoner` | `POST /chat/completions` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `deepseek/deepseek-r1` | `POST /chat/completions` |
| **Groq** | `GROQ_API_KEY` | `deepseek-r1-distill-llama-70b` | `POST /openai/v1/chat/completions` |
| **Mistral** | `MISTRAL_API_KEY` | `mistral-large-latest` | `POST /v1/chat/completions` |
| **Together AI** | `TOGETHER_API_KEY` | `deepseek-ai/DeepSeek-R1` | `POST /v1/chat/completions` |
| **Cohere** | `COHERE_API_KEY` | `command-r-plus-08-2024` | `POST /v2/chat` |
| **Generic (Local)** | None required | `default` | `POST /v1/chat/completions` |

To list all supported providers and check which keys are currently detected:
```bash
python run_benchmark.py --list-providers
```

---

## Batch Benchmark Configuration

RSI-Bench supports defining multiple benchmark runs in a single, gitignored configuration file (`config.yaml` or `config.json`). Tracked example templates are provided as `config.example.yaml` and `config.example.json`.

### 1. Quick Setup
Copy the template to your local config:
```bash
cp config.example.yaml config.yaml   # or copy on Windows
```

Edit `config.yaml` with your provider API keys and desired benchmark evaluations. Secrets in `config.yaml` are protected by `.gitignore`.

### 2. Running in Batch
```bash
# Run all enabled benchmarks defined in config.yaml / config.json:
python run_benchmark.py

# Explicitly specify a config file:
python run_benchmark.py --config my_benchmarks.yaml

# Run offline mock simulation for every run in the config (zero API cost):
python run_benchmark.py --config config.example.yaml --mock

# Filter runs by name or tag substring:
python run_benchmark.py --filter reasoning

# Override turn count for all runs in the batch:
python run_benchmark.py --batch --turns 5
```

---

## Usage Examples

### 1. Offline Simulation (No API key needed)
```bash
python run_benchmark.py --mock --turns 3
```

### 2. Google Gemini Interactions API
```bash
python run_benchmark.py --provider gemini_interactions --model gemini-2.5-flash --turns 3
```

### 3. Anthropic Messages (with Prompt Caching & Thinking)
```bash
python run_benchmark.py --provider anthropic --model claude-3-7-sonnet-20250219 --turns 3 --thinking-budget 1024
```

### 4. OpenAI Responses API
```bash
python run_benchmark.py --provider openai_responses --model gpt-4o --turns 3
```

### 5. OpenAI Regular Chat Route (Reasoning Model)
```bash
python run_benchmark.py --provider openai_chat --model o3-mini --turns 3
```

### 6. OpenAI Text Completions Route
```bash
python run_benchmark.py --provider openai_completion --model gpt-3.5-turbo-instruct --turns 3
```

### 7. Google Gemini Content API (generateContent)
```bash
python run_benchmark.py --provider gemini --model gemini-2.5-flash --turns 3
```

### 8. DeepSeek Reasoner
```bash
python run_benchmark.py --provider deepseek --model deepseek-reasoner --turns 3
```

### 9. OpenRouter
```bash
python run_benchmark.py --provider openrouter --model deepseek/deepseek-r1 --turns 3
```

### 10. Local Ollama / vLLM Endpoint
```bash
python run_benchmark.py --provider generic --base-url http://localhost:11434/v1 --model llama3.3:70b --turns 3
```

### 11. Benchmark All Configured Providers
```bash
python run_benchmark.py --all-configured --turns 3
```

---

## Output Traces and Artifacts

Every benchmark execution produces structured output in the `results/` directory:

1. **`results/batch_<batch_id>.json`**: Complete machine-readable record of an entire batch execution.
2. **`results/batch_<batch_id>.md`**: Formatted aggregate report with markdown comparison tables across all models in the batch.
3. **`results/traces/<provider>_<model>_<run_id>.json`**: Complete machine-readable individual run record including:
   - Run configuration and parameters
   - Parsed integers list (`[42, -18, 90]`)
   - Latency per turn (ms)
   - Prompt caching metrics (`cached_tokens`, `cache_creation_tokens`)
   - Reasoning/thinking traces
   - Full raw request and response payloads
4. **`results/traces/<provider>_<model>_<run_id>.md`**: Formatted Markdown document with collapsible thinking blocks and turn-by-turn tables.
5. **`results/benchmark_summary.csv`**: Appended summary log row for aggregate performance and latency tracking across models.

## Visualization and Benchmark Spoof Charts

RSI-Bench includes a visualization system (`generate_charts.py` and `rsi_bench/visualization.py`) that renders high-fidelity benchmark charts in HTML and automatically renders crisp PNG images via headless Google Chrome or Microsoft Edge.

### 1. Artificial Analysis Intelligence Index Bar Chart
Replicates the visual design of the Artificial Analysis Intelligence Index benchmark:
- Exact typography, header, and Artificial Analysis spark logo
- Rounded bar corners with integer scores inside the bars
- Color-coded brand palettes for all frontier labs (Anthropic, OpenAI, Google, Meta, Moonshot, xAI, Alibaba, DeepSeek, Zhipu, Xiaomi, Ling, MiniMax, StepFun, Mistral, Horizon, Beam, Nvidia, Inkling)
- Diagonal crosshatch pattern for models without public APIs (`Muse Wonder Full (max)`)
- Lab vector logos and 45-degree angled model labels

### 2. Multi-Turn Dynamic Performance Trajectory Line Graph
Shows each model's turn-by-turn integer outputs and cumulative prefix sum trajectories from turn 1 to turn $N$:
> **The Spoof Design**: In accordance with the project's design, the graph axes are **completely unlabeled** (no axis titles like "Turns", "Steps", "Score", "Integer", or "Prefix Sum"). It presents integer outputs and cumulative prefix sums as serious-looking frontier AI trajectory curves.

### 3. Usage

```bash
# Generate charts from latest benchmark results or mock reference data:
python generate_charts.py

# Generate reference charts matching the Artificial Analysis index image (29 models, scores 58 to 6):
python generate_charts.py --reference

# Load specific batch JSON or summary CSV:
python generate_charts.py --data results/batch_8472fbc647.json
python generate_charts.py --data results/benchmark_summary.csv

# Customize turn count for simulated trajectories:
python generate_charts.py --turns 5

# HTML only (skip headless browser PNG screenshot):
python generate_charts.py --no-png

# Automatically generate charts as part of a benchmark run:
python run_benchmark.py --mock --config config.yaml --charts
```

Generated outputs are saved in `results/charts/`:
- `results/charts/artificial_analysis_intelligence_index.html` & `.png`
- `results/charts/model_trajectory_index.html` & `.png`

---

## Supported Models (All 28 Public Models via OpenRouter)

All 28 models with publicly available APIs from the Artificial Analysis Intelligence Index are configured in `config.example.yaml` and `config.yaml` via OpenRouter:

| # | Model Name | Provider | OpenRouter Model ID | Reference Score |
|---|---|---|---|---|
| 1 | Claude Opus 5.5 (max with fallback) | Anthropic | `anthropic/claude-3-opus` | 58 |
| 2 | GPT-6 Astra (max) | OpenAI | `openai/gpt-4o` | 57 |
| 3 | GPT-6.1 Sol (max) | OpenAI | `openai/o1` | 55 |
| 4 | Claude Sonnet 5.5 (max with fallback) | Anthropic | `anthropic/claude-3.7-sonnet` | 54 |
| 5 | GPT-6.1 Terra (max) | OpenAI | `openai/o3-mini` | 51 |
| 6 | Gemini 4 Argon (high) | Google | `google/gemini-2.0-flash-001` | 50 |
| * | *Muse Wonder Full (max)* | *Meta* | *Omitted (No Public API)* | *50* |
| 7 | Claude Fable 5.1 (max with fallback) | Anthropic | `anthropic/claude-3.5-sonnet` | 49 |
| 8 | Kimi K3.1 Pro | Moonshot | `moonshotai/kimi-k3.1-pro` | 46 |
| 9 | Muse Wonder (max) | Meta | `meta-llama/llama-3.3-70b-instruct` | 43 |
| 10 | Claude Haiku 5.5 (max) | Anthropic | `anthropic/claude-3.5-haiku` | 36 |
| 11 | Grok 4.7 (xhigh) | xAI | `x-ai/grok-2` | 34 |
| 12 | Qwen3.8 Max (0902) | Alibaba | `qwen/qwen-2.5-72b-instruct` | 34 |
| 13 | DeepSeek V4.1 Flash 1017 (max) | DeepSeek | `deepseek/deepseek-r1` | 32 |
| 14 | GLM-5.3 (max) | Zhipu | `zhipu/glm-4-plus` | 32 |
| 15 | Gemini 3.8 Flash (high) | Google | `google/gemini-2.0-flash-lite-preview-02-05` | 31 |
| 16 | MiMo-V2.6-Pro | Xiaomi | `xiaomi/mimo-v2.6-pro` | 30 |
| 17 | Ling 3.1 Flash 1019 | Ling | `ling/ling-3.1-flash` | 29 |
| 18 | MiniMax-M3.1-Flash | MiniMax | `minimax/minimax-01` | 29 |
| 19 | Step 5 Preview | StepFun | `stepfun/step-2-16k` | 29 |
| 20 | GPT-6 Luna (max) | OpenAI | `openai/gpt-4o-mini` | 28 |
| 21 | Mistral Large 4 Preview | Mistral | `mistralai/mistral-large-2411` | 25 |
| 22 | Muse Spark Open (xhigh) | Meta | `meta-llama/llama-3.1-405b-instruct` | 25 |
| 23 | Qwen3.8 27B (xhigh) | Alibaba | `qwen/qwen-2.5-32b-instruct` | 20 |
| 24 | K2 Horizon 375B A23B | Horizon | `horizon/k2-375b-a23b` | 18 |
| 25 | Beam 1.0 | Beam | `beam/beam-1.0` | 18 |
| 26 | Nemotron 3.5 Super VL | Nvidia | `nvidia/llama-3.1-nemotron-70b-instruct` | 14 |
| 27 | Inkling (xhigh) | Inkling | `inkling/inkling-xhigh` | 12 |
| 28 | Muse Glimmer (high) | Meta | `meta-llama/llama-3.2-3b-instruct` | 6 |

### Required API Keys
- **When using OpenRouter (`provider: openrouter`)**: Only **`OPENROUTER_API_KEY`** is required! All 28 models route through OpenRouter.
- **When using direct provider APIs**:
  - Anthropic: `ANTHROPIC_API_KEY`
  - OpenAI: `OPENAI_API_KEY`
  - Google Gemini: `GEMINI_API_KEY` or `GOOGLE_API_KEY`
  - DeepSeek: `DEEPSEEK_API_KEY`
  - Groq: `GROQ_API_KEY`
  - Mistral: `MISTRAL_API_KEY`
  - Together AI: `TOGETHER_API_KEY`
  - Cohere: `COHERE_API_KEY`
- **When running simulation**: Zero API keys are needed! Pass `--mock`:
  ```bash
  python run_benchmark.py --mock --config config.yaml
  ```

---

## Running Tests

Execute the complete test suite with:

```bash
python -m pytest
```

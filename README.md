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
├── run_benchmark.py           # Quick CLI runner script
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

1. **`results/traces/<provider>_<model>_<run_id>.json`**: Complete machine-readable record including:
   - Run configuration and parameters
   - Parsed integers list (`[42, -18, 90]`)
   - Latency per turn (ms)
   - Prompt caching metrics (`cached_tokens`, `cache_creation_tokens`)
   - Reasoning/thinking traces
   - Full raw request and response payloads
2. **`results/traces/<provider>_<model>_<run_id>.md`**: Formatted Markdown document with collapsible thinking blocks and turn-by-turn tables.
3. **`results/benchmark_summary.csv`**: Appended summary log row for aggregate performance and latency tracking across models.

---

## Running Tests

Execute the complete test suite with:

```bash
python -m pytest
```

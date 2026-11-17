# FDE Sprint API

A small, production-style FastAPI backend that sends chat messages to Large Language Model (LLM) providers through one clean API.

It is the Day 1 foundation of a 3-week Forward Deployed Engineer (FDE) sprint. Later days add prompt management, structured outputs, retrieval (RAG), agents, MCP integrations, evaluation and deployment on top of it.

---

## Features

- **One API, multiple providers:** any OpenAI-compatible provider (currently **Groq**) and **Anthropic**, behind a single `/chat` endpoint.
- **Switch providers through config only:** change the base URL, key and model in `.env`, with no code changes.
- **Typed, validated configuration** with Pydantic Settings; secrets are hidden as `**********` when printed or logged.
- **Structured JSON logging**, with token usage and latency recorded for every LLM call.
- **Safe defaults:** request timeouts, automatic retries, input length limits and output token limits.
- **Clean error handling:** provider failures are translated into clear HTTP status codes (429, 502, 503, 504).
- **Interactive API docs** (Swagger UI) generated automatically.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Web framework | FastAPI |
| Server | Uvicorn |
| Validation and config | Pydantic, pydantic-settings |
| LLM SDKs | OpenAI Python SDK (used with Groq), Anthropic Python SDK |
| LLM provider (development) | Groq, model `openai/gpt-oss-120b` |

---

## Project structure

```
fde-sprint/
├── app/
│   ├── __init__.py          # Makes `app` a Python package
│   ├── main.py              # FastAPI app and endpoints (/health, /chat)
│   ├── config.py            # Typed settings loaded from .env
│   ├── logging_config.py    # JSON logging setup
│   ├── llm_clients.py       # OpenAI-compatible and Anthropic client wrappers
│   └── schemas.py           # Request and response models for the API
├── scripts/
│   ├── __init__.py
│   └── try_llm.py           # Quick terminal check that calls each provider
├── docs/
│   ├── provider-comparison.md
│   └── decision-log.md
├── logs/
│   └── day-01.md            # Daily progress log
├── .env.example             # Template for environment variables (no secrets)
├── .gitignore
├── requirements.txt         # Pinned dependencies
└── README.md
```

---

## Prerequisites

- **Python 3.11 or higher** (developed on 3.14)
- **Git**
- An API key for at least one provider:
  - **Groq** (free tier): [console.groq.com](https://console.groq.com)
  - **OpenAI** (paid): [platform.openai.com](https://platform.openai.com)
  - **Anthropic** (small starter credit): [console.anthropic.com](https://console.anthropic.com)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/fde-sprint.git
cd fde-sprint
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**

```powershell
py -3.14 -m venv .venv
.venv\Scripts\activate
```

> If PowerShell says *"running scripts is disabled"*, run this once and try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your terminal prompt should now start with `(.venv)`.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the template:

```powershell
# Windows
copy .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

Then open `.env` and fill in your keys (see [Configuration](#configuration)).

> ⚠️ **Never commit `.env`.** It is already listed in `.gitignore`.

---

## Configuration

All settings are read from `.env` (or from real environment variables, which take priority).

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | No | `dev` | One of `dev`, `staging`, `prod`. Any other value stops the app at startup. |
| `LOG_LEVEL` | No | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `OPENAI_API_KEY` | For `provider: "openai"` | — | Key for the OpenAI-compatible provider (currently a **Groq** key). |
| `OPENAI_BASE_URL` | No | OpenAI's URL | Server to call. For Groq: `https://api.groq.com/openai/v1`. Leave empty for real OpenAI. |
| `OPENAI_MODEL` | No | `gpt-5-nano` | Model name on that server, e.g. `openai/gpt-oss-120b` on Groq. |
| `ANTHROPIC_API_KEY` | For `provider: "anthropic"` | — | Anthropic API key (starts with `sk-ant-api`). |
| `ANTHROPIC_MODEL` | No | `claude-haiku-5-5` | Anthropic model name. |
| `LLM_TIMEOUT_SECONDS` | No | `30.0` | Maximum time to wait for a provider response. |
| `LLM_MAX_OUTPUT_TOKENS` | No | `1000` | Maximum tokens in a reply (cost safety limit). |

### Example `.env` for Groq

```
ENVIRONMENT=dev
LOG_LEVEL=INFO

OPENAI_API_KEY=your-groq-key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-120b

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-5-5
```

### Switching from Groq to real OpenAI

Change only `.env`; no code changes needed:

```
OPENAI_API_KEY=your-openai-key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-5-nano
```

> Settings are cached when the app starts. **Restart the server after editing `.env`.**

---

## Running the API

```bash
uvicorn app.main:app --reload
```

- The API runs at **http://127.0.0.1:8000**
- Swagger UI (interactive docs): **http://127.0.0.1:8000/docs**
- `--reload` restarts the server automatically when a `.py` file changes. Use it in development only.

### Quick provider check (without the API)

```bash
python -m scripts.try_llm
```

This calls each configured provider once and prints the reply, token counts and latency.

> Run it with `python -m` from the project root. Running `python scripts/try_llm.py` directly fails with `No module named 'app'`.

---

## API endpoints

### `GET /health`

Checks that the server is running and shows which providers are configured. It never shows the keys themselves.

**Response `200`**

```json
{
  "status": "ok",
  "environment": "dev",
  "openai_configured": true,
  "anthropic_configured": false
}
```

> `configured` only means a key is present, not that it is valid.

### `POST /chat`

Sends one message to the chosen provider and returns the reply with usage metrics.

**Request body**

| Field | Type | Required | Rules |
|---|---|---|---|
| `message` | string | Yes | 1–4000 characters |
| `provider` | string | No | `"openai"` (default) or `"anthropic"` |

> `"openai"` means the **OpenAI-compatible** code path. It calls whichever server `OPENAI_BASE_URL` points to (currently Groq).

**Example request**

```json
{
  "message": "In one sentence, what is a Forward Deployed Engineer?",
  "provider": "openai"
}
```

**Response `200`**

```json
{
  "provider": "openai-compatible",
  "model": "openai/gpt-oss-120b",
  "reply": "A Forward Deployed Engineer is a software engineer who works directly with customers...",
  "input_tokens": 98,
  "output_tokens": 78,
  "latency_ms": 881.7
}
```

**Calling it from the terminal**

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"message": "What is an FDE?", "provider": "openai"}'
```

macOS / Linux:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is an FDE?", "provider": "openai"}'
```

---

## Error responses

| Code | Meaning | When it happens | What the client should do |
|---|---|---|---|
| **422** | Unprocessable Content | Invalid input: empty or too-long `message`, unknown `provider` | Fix the request |
| **429** | Too Many Requests | The provider is rate-limiting this server | Wait and retry |
| **502** | Bad Gateway | The provider returned an error (e.g. invalid server key, wrong model name, provider outage) | Retry later; the server team checks the logs |
| **503** | Service Unavailable | The chosen provider has no API key configured | Use another provider, or the server team adds the key |
| **504** | Gateway Timeout | The provider did not answer within `LLM_TIMEOUT_SECONDS` | Retry |

Error responses use FastAPI's standard format:

```json
{ "detail": "Provider 'anthropic' is not configured on this server." }
```

Responses to clients are deliberately short and safe. Full details (error type, provider status code) are written to the server logs.

---

## Logging

The app writes **one JSON object per line** to the terminal, so logs can be searched and filtered (for example in AWS CloudWatch).

```json
{"time": "2026-11-17T15:41:36.517401+00:00", "level": "INFO", "logger": "app.llm_clients", "message": "llm_call_completed", "provider": "openai-compatible", "model": "openai/gpt-oss-120b", "input_tokens": 99, "output_tokens": 109, "latency_ms": 959.9}
```

| Event | Level | Meaning |
|---|---|---|
| `app_starting` | INFO | App started; shows environment and configured providers |
| `health_checked` | INFO | `/health` was called |
| `llm_call_completed` | INFO | An LLM call succeeded; includes tokens and latency |
| `provider_not_configured` | WARNING | `/chat` was called for a provider without a key |
| `llm_timeout` | WARNING | The provider was too slow |
| `llm_rate_limited` | WARNING | The provider rate-limited the request |
| `llm_provider_error` | ERROR | Any other provider failure; includes error type and status |

**Privacy rule:** logs contain metadata only (provider, model, tokens, latency). **Prompts, replies and API keys are never logged**, because they may contain customer data.

Uvicorn's own server logs remain in plain-text format.

---

## Design decisions

Key decisions and their reasons are recorded in [`docs/decision-log.md`](docs/decision-log.md). Highlights:

- **Chat Completions API instead of OpenAI's Responses API:** it is the format other providers copy, so one code path works with Groq, OpenAI and others.
- **Adapter pattern:** every provider returns the same internal `LLMResult`, so the rest of the app never depends on one vendor.
- **Separate public and internal models:** `ChatResponse` is the public API contract; `LLMResult` can change without breaking clients.

Provider evaluation (cost, latency, limits, data policy): [`docs/provider-comparison.md`](docs/provider-comparison.md).

---

## Known limitations

- **Anthropic is not configured yet** (no API key), so `provider: "anthropic"` returns `503`.
- **No authentication:** anyone who can reach the server can call `/chat`. Planned for Day 12.
- **No automated tests yet.** Planned for Day 9 (pytest and HTTPX).
- **No streaming:** replies arrive all at once. Planned for Day 2.
- **Single message only:** there is no conversation history between calls.
- **Free-tier rate limits** on Groq can return `429` under heavy use.
- Uvicorn's own logs are plain text, not JSON.

---

## Roadmap

| Day | Planned addition |
|---|---|
| 2 | Versioned prompt files, structured JSON output, streaming, tool calling |
| 3 | Embeddings and semantic search with PostgreSQL + pgvector |
| 4 | Full RAG pipeline with citations |
| 6+ | MCP server and third-party integrations |
| 9 | Automated tests, hardening |
| 11–13 | Docker, AWS deployment, authentication, CI/CD, evals |

---

## Progress logs

Daily logs are in [`logs/`](logs/), starting with [`logs/day-01.md`](logs/day-01.md).

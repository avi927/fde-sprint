# FDE Sprint API

A production-style FastAPI backend for an AI customer-support assistant: LLM chat (with
streaming), structured ticket triage, tool calling, and semantic + keyword search over a
help-centre knowledge base stored in PostgreSQL with pgvector.

Built during a 3-week Forward Deployed Engineer (FDE) sprint. Later days add RAG with
citations, agents, MCP integrations, evaluation in CI and AWS deployment.

---

## Features

- **LLM chat** through an OpenAI-compatible provider (currently **Groq**) or Anthropic, with
  timeouts, retries and clean error codes — plus **streaming** (Server-Sent Events).
- **Ticket triage** (`/triage`): returns validated JSON (category, priority, sentiment, summary,
  needs_human) using versioned prompts (v1–v4), Pydantic validation and retry with feedback.
- **Tool calling** (`/assistant`): the model can look up order status through a validated tool,
  with a step limit.
- **Semantic and keyword search** (`/search`) over 20 help-centre articles, with category filters.
- **Local embeddings** (FastEmbed, `BAAI/bge-small-en-v1.5`) — no API key, data stays local.
- **PostgreSQL 18 + pgvector** in Docker, with **SQL migrations** and **idempotent ingestion**.
- **Evals**: triage prompt eval (per-field accuracy) and search eval (Hit@1, Hit@3, MRR).
- **Safety**: delimiters + tag stripping against prompt injection, strict output schemas,
  no secrets in prompts, metadata-only logging.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| API | FastAPI, Uvicorn, Pydantic, pydantic-settings |
| LLM SDKs | OpenAI Python SDK (used with Groq), Anthropic Python SDK |
| LLM (development) | Groq, `openai/gpt-oss-120b` |
| Embeddings | FastEmbed (ONNX Runtime), `BAAI/bge-small-en-v1.5` (384 dims) |
| Database | PostgreSQL 18 + pgvector 0.8 (Docker), psycopg 3 |
| Infrastructure | Docker Desktop, Docker Compose |

---

## Project structure

```
fde-sprint/
├── app/
│   ├── main.py            # FastAPI app, error handlers, endpoints
│   ├── config.py          # Typed settings from .env
│   ├── logging_config.py  # JSON logging
│   ├── llm_clients.py     # OpenAI-compatible + Anthropic clients, streaming
│   ├── prompts.py         # Loads versioned prompt files
│   ├── schemas.py         # Request/response models (the API contract)
│   ├── triage.py          # Triage with validation + retry
│   ├── tools.py           # Tools the assistant can call (get_order_status)
│   ├── assistant.py       # Tool-calling loop
│   ├── streaming.py       # LLM stream → Server-Sent Events
│   ├── embeddings.py      # Embedding model adapter
│   ├── db.py              # Database connections (pgvector registered)
│   └── search.py          # Semantic + keyword search
├── prompts/               # triage_v1–v4.md, chat_v1.md, assistant_v1.md
├── migrations/            # 001–004 SQL migrations
├── data/
│   └── knowledge_base.json  # 20 help-centre articles
├── evals/
│   ├── triage_cases.json
│   ├── search_cases.json
│   └── results/           # Saved eval runs (evidence)
├── scripts/               # Ingestion, migrations, evals, manual test tools
├── docs/                  # decision-log.md, provider-comparison.md, safety-notes.md
├── logs/                  # day-01.md, day-02.md, day-03.md
├── docker-compose.yml
├── progress.md
├── .env.example
└── requirements.txt
```

---

## Prerequisites

- **Python 3.11+** (developed on 3.14)
- **Docker Desktop** (running)
- **Git**
- A **Groq** API key (free tier) — or an OpenAI key; Anthropic optional

---

## Setup

### 1. Clone and create a virtual environment

```powershell
git clone https://github.com/<your-username>/fde-sprint.git
cd fde-sprint
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(macOS/Linux: `python3 -m venv .venv` and `source .venv/bin/activate`.)

### 2. Configure

```powershell
copy .env.example .env
```

Fill in your API key and a local database password (see [Configuration](#configuration)).

### 3. Start the database

```powershell
docker compose up -d
docker compose ps      # wait for "healthy"
```

### 4. Create the schema and load the knowledge base

```powershell
python -m scripts.migrate     # applies migrations 001–004
python -m scripts.ingest      # embeds and stores 20 articles (first run downloads the model, ~67 MB)
python -m scripts.db_check    # should show localhost:5433, Debian/linux, pgvector 0.8.x
```

### 5. Run the API

```powershell
uvicorn app.main:app --reload
```

Swagger UI: **http://127.0.0.1:8000/docs**

> **Port note:** the Docker database is published on **5433** (not 5432) to avoid clashing
> with a locally installed PostgreSQL. If you connect with pgAdmin/DBeaver, use port 5433.

---

## Configuration

Settings come from `.env` (real environment variables take priority). Restart the server after
changes — settings are cached.

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `dev` | `dev`, `staging` or `prod` (anything else stops the app) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `OPENAI_API_KEY` | — | Key for the OpenAI-compatible provider (currently a Groq key) |
| `OPENAI_BASE_URL` | OpenAI | `https://api.groq.com/openai/v1` for Groq |
| `OPENAI_MODEL` | `gpt-5-nano` | e.g. `openai/gpt-oss-120b` on Groq |
| `ANTHROPIC_API_KEY` | — | Optional |
| `ANTHROPIC_MODEL` | `claude-haiku-5-5` | Anthropic model |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Max wait for a provider response |
| `LLM_MAX_OUTPUT_TOKENS` | `1000` | Max tokens per reply (includes hidden reasoning) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | — | Used by Docker **only when the volume is first created** |
| `DATABASE_URL` | — | `postgresql://<user>:<password>@localhost:5433/fde_sprint` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Changing it requires a migration + re-ingestion |
| `EMBEDDING_DIMENSIONS` | `384` | Must match the model and the `vector(384)` column |
| `EMBEDDING_USE_QUERY_PREFIX` | `true` | Add the BGE retrieval instruction to search queries |

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Server alive + which LLM providers are configured |
| POST | `/chat` | One message → one reply (`provider`: `openai` or `anthropic`) |
| POST | `/chat/stream` | Same, streamed as Server-Sent Events (use curl or `scripts/stream_client.py`; Swagger shows it only at the end) |
| POST | `/triage` | Support ticket → validated JSON triage (`prompt_version` v1–v4, default v4) |
| POST | `/assistant` | Customer question → answer, calling `get_order_status` when needed |
| POST | `/search` | Knowledge base search (`mode`: `semantic` or `keyword`, optional `category`, `top_k` 1–20) |

> `provider: "openai"` means the **OpenAI-format code path**; the server it calls is set by
> `OPENAI_BASE_URL` (currently Groq).

### Example: search

```json
POST /search
{"query": "How do I get my money back?", "top_k": 3, "mode": "semantic"}
```

```json
{
  "query": "How do I get my money back?",
  "top_k": 3,
  "category": null,
  "mode": "semantic",
  "results": [
    {"slug": "refund-policy", "title": "Refund policy", "category": "billing", "score": 0.673, "content": "..."}
  ],
  "embedding_ms": 16.5,
  "db_ms": 45.5
}
```

Scores are only comparable **within the same mode**.

---

## Error responses

| Code | When |
|---|---|
| 422 | Invalid input (validation) |
| 429 | The LLM provider is rate-limiting us |
| 500 | Server configuration error (e.g. missing prompt file) |
| 502 | LLM provider error; triage couldn't produce valid JSON after 3 attempts; assistant hit its step limit |
| 503 | LLM provider not configured; database not configured or unreachable |
| 504 | LLM provider timeout |

Clients get short, safe messages (`{"detail": "..."}`); details go to the server logs.

---

## Scripts

| Command | Purpose |
|---|---|
| `python -m scripts.migrate` | Apply database migrations (idempotent) |
| `python -m scripts.ingest` | Embed and upsert the knowledge base (idempotent) |
| `python -m scripts.db_check` | Show target DB, server version, pgvector version |
| `python -m scripts.run_eval [v3 v4]` | Triage prompt eval (per-field accuracy) |
| `python -m scripts.run_search_eval` | Search eval: keyword vs semantic (Hit@1, Hit@3, MRR) |
| `python -m scripts.try_llm` | Call each LLM provider once |
| `python -m scripts.try_prompts "ticket"` | Compare triage prompt versions on one ticket |
| `python -m scripts.stream_client "message"` | Watch `/chat/stream` live |
| `python -m scripts.embedding_playground` | Explore embeddings and similarity |

---

## Evals section:-
- python -m scripts.run_search_eval    # retrieval quality: Hit@1, Hit@3, MRR per strategy
- python -m scripts.run_rag_eval       # answer quality: correct, cited, IDK, hallucination

## Evaluation results (latest)

| Eval | Result | Evidence |
|---|---|---|
| Triage prompts (12 cases) | v4: **12/12**, v3: 10/12 | `evals/results/triage_*.json` |
| Search (10 queries) | Semantic Hit@3 **100%**, keyword **80%** | `evals/results/search_*.json` |

Caveat: the search eval is small (20 docs) and shows a ceiling effect; a harder set is planned.

---

## Logging

One JSON object per line; **metadata only** — prompts, replies, search queries and keys are
never logged. Key events: `app_starting`, `embedding_model_ready`, `llm_call_completed`,
`triage_completed`, `triage_invalid_output`, `tool_called`, `assistant_completed`,
`stream_completed`, `search_completed`, and error events (`llm_timeout`, `llm_rate_limited`,
`llm_provider_error`, `database_unavailable`, …).

---

## Design decisions and docs

- [`docs/decision-log.md`](docs/decision-log.md) — every design choice, why, and what was rejected
- [`docs/provider-comparison.md`](docs/provider-comparison.md) — LLM provider comparison
- [`docs/safety-notes.md`](docs/safety-notes.md) — attacks tested and defenses
- [`progress.md`](progress.md) — daily status (Green/Amber/Red)
- [`logs/`](logs/) — daily logs

---

## Known limitations

- Anthropic is not configured (no API key) → `provider: "anthropic"` returns 503.
- **No authentication** — planned for Day 12.
- **No automated tests** (pytest) yet — planned for Day 9.
- Streaming supports only the OpenAI-compatible path.
- No conversation memory between `/chat` calls.
- Groq free-tier rate limits can return 429 (and slow down evals).
- New database connection per search (~45 ms) — connection pool planned.
- Embeddings are **English only**; semantic search is weak on negation.
- The app connects as the `postgres` superuser — dedicated limited user planned (Day 12).
- Cost per request in $ is not tracked yet (tokens are) — planned for Day 13.

---

## Roadmap

| Day | Next |
|---|---|
| 4 | RAG pipeline: chunking, hybrid search, reranking, answers with citations, "I don't know" |
| 5 | RAG v1 demo, break-it session, track choice (MCP & integrations) |
| 6–10 | MCP server + third-party integrations, n8n, webhooks |
| 11–13 | Docker for the API, AWS deployment, auth, CI/CD, evals in CI |
# Decision Log

Each entry records **what** we decided, **why**, what we **rejected**, and **when to revisit** it.
Entries with numbers link to the evidence (eval result files in `evals/results/`).

---

## Day 1 — 17 Nov 2026

### 2026-11-17 — Use Chat Completions API instead of OpenAI Responses API

- **Decision:** Call LLMs through the OpenAI SDK's Chat Completions endpoint.
- **Why:** It is the format other providers copy (Groq, Gemini, Mistral), so the same code
  works across providers by changing only config (base URL, key, model).
- **Rejected:** Responses API — OpenAI recommends it for new projects and it has built-in
  tools, but other providers don't fully support it.
- **Revisit when:** We commit to OpenAI only, or need Responses-only features.

### 2026-11-17 — Use Groq for development

- **Decision:** Use Groq (`openai/gpt-oss-120b`) through the OpenAI-compatible API for development.
- **Why:** Free tier with no payment method, fast (~0.9–1 s per short call), OpenAI-compatible,
  so switching to OpenAI later is a config change only.
- **Rejected:** Paid OpenAI (no free tier); Anthropic (no API key / credit available yet).
- **Revisit when:** We handle real customer data (check data policy), need higher rate limits,
  or deploy to production (Day 12).

### 2026-11-17 — Keep `provider: "openai"` as the API value for the OpenAI-format code path

- **Decision:** The `/chat` request field `provider` keeps the value `"openai"`, meaning
  "the OpenAI SDK / OpenAI-format API", whose server is set by `OPENAI_BASE_URL` (currently Groq).
- **Why:** Switching between Groq and OpenAI is a config change with no API change for clients.
- **Rejected:** `"groq"` (ties the public API to one vendor); `"openai_compatible"` (clearer,
  but not needed now — documented in the README instead).
- **Trade-off:** The name can mislead readers into thinking we call OpenAI; mitigated by the
  README and Swagger description.
- **Revisit when:** We expose the API to external clients.

### 2026-11-17 — Translate provider errors into our own HTTP status codes

- **Decision:** Map provider failures to 503 (not configured), 504 (timeout), 429 (rate limit),
  502 (any other provider error). Detailed info goes to logs; clients get short, safe messages.
- **Why:** The client should not see a provider's 401 (it's our key, not theirs); raw errors
  leak internal details; clear codes tell clients what to do.
- **Rejected:** Passing provider errors through unchanged.

### 2026-11-17 — Typed configuration from `.env` with pydantic-settings

- **Decision:** All settings live in one typed `Settings` class; secrets use `SecretStr`;
  allowed values use `Literal`; empty values are treated as unset.
- **Why:** Fails fast at startup on bad config; keeps secrets out of code and logs; one place
  to see every setting.
- **Rejected:** Hardcoded values; reading `os.environ` directly across files.

### 2026-11-17 — JSON structured logging, metadata only

- **Decision:** All app logs are one-line JSON with event names (`llm_call_completed`).
  We log provider, model, tokens and latency — never prompts, replies or keys.
- **Why:** JSON logs can be searched and filtered (e.g. CloudWatch); prompts may contain
  customer data, so logging them is a privacy risk.
- **Rejected:** Plain-text logs; logging full prompts and responses.

---

## Day 2 — 18 Nov 2026

### 2026-11-18 — Store prompts as versioned files

- **Decision:** Prompts live in `prompts/<name>_<version>.md` and are loaded by
  `app/prompts.py`. Old versions are never edited; a change means a new version file.
- **Why:** Versions can be compared with evals, rolled back, reviewed in pull requests,
  and edited by non-developers.
- **Rejected:** Prompts as strings inside Python code.

### 2026-11-18 — Validate model output with Pydantic and retry with feedback

- **Decision:** `/triage` validates the model's JSON against `TriageResult`
  (`Literal` values, `extra="forbid"`). On failure, retry with Pydantic's error messages
  as feedback. Maximum 3 attempts, then return 502. Strip markdown code fences in code first.
- **Why:** LLM output is untrusted and can break format even with good prompts. Pydantic's
  errors teach the model the allowed values (v1 recovered on attempt 2). A cheap code fix
  (fence stripping) comes before a paid retry.
- **Rejected:** Trusting raw output; unlimited retries (cost and latency risk).
- **Evidence:** v1 needed 1.90 attempts on average vs 1.00 for v2–v3
  (`triage_20261118-190951.json`).

### 2026-11-18 — Our own validation instead of relying only on provider JSON modes

- **Decision:** Validate with Pydantic in our code, regardless of provider.
- **Why:** Works with any provider and model; acts as a safety net even when a JSON mode is on.
- **Rejected:** Depending only on a provider's structured-output feature (support varies).
- **Revisit when:** Format failures become frequent → add provider JSON mode as an extra layer.

### 2026-11-18 — Central exception handlers instead of try/except in each endpoint

- **Decision:** Register FastAPI exception handlers once (`@app.exception_handler`) for
  provider errors, `TriageFailedError` and `PromptNotFoundError`.
- **Why:** DRY — every endpoint (`/chat`, `/triage`, future ones) gets the same consistent
  error responses and logging.
- **Rejected:** Copying the `except` chain into every endpoint.
- **Trade-off:** The 503 message no longer names the provider (the handler doesn't know it).

### 2026-11-18 — Eval design: score code-checkable fields, allow acceptable values

- **Decision:** The triage eval scores `category`, `priority`, `sentiment` and `needs_human`
  by exact match. Subjective fields may list several acceptable values. `summary` is not
  scored yet. Each case has a `note` explaining its expected answer.
- **Why:** Exact scoring is cheap, repeatable and objective; forcing a single answer for a
  fuzzy label would be unfair.
- **Rejected:** Judging outputs by eye (not repeatable); scoring the summary without a judge.
- **Revisit when:** We add LLM-as-judge for summaries (later in the sprint).
- **Known weakness:** Sentiment scores 100% for every version — the acceptable lists may be
  too generous or the cases too easy.

### 2026-11-18 — Prompt v3 over v1 and v2

- **Decision:** v3 (role + allowed values + business rules + steps + 3 few-shot examples)
  replaces v1/v2.
- **Why:** On 10 cases: v1 4/10, v2 6/10, v3 9/10. v1 obeyed an indirect prompt injection;
  v2 and v3 resisted. v1 was also slowest (1,647 ms avg) because of retries.
- **Trade-off:** v3 uses ~2.6× v2's input tokens (7,081 vs 2,701 for 10 tickets) —
  accepted for +30 points of accuracy at a fraction of a cent per ticket.
- **Evidence:** `triage_20261118-190951.json`

---

## Day 2 (continued) — 19 Nov 2026

### 2026-11-19 — Promote triage prompt v4 to default

- **Decision:** v4 is the default `prompt_version` for `/triage`.
- **What changed from v3:** One rule only — "high" now includes "a paid feature or service
  that works only partly or keeps failing (still usable, but badly)".
- **Why:** On 12 cases (incl. 2 new boundary cases), 2 runs:
  - Run 1: v3 10/12, v4 11/12 (the one v4 miss was a placeholder bug in the dataset)
  - Run 2: v3 10/12, v4 **12/12**, priority accuracy 83% → 100%
  - No regressions: `account-hacked` and `legal-threat` stayed `urgent`.
  - v3's answer on `premium-logout` was unstable across runs (urgent, urgent, medium);
    v4's explicit rule made it consistent.
- **Rejected:** Keeping v3 (misclassifies partly broken paid features, inconsistently).
- **Note:** v4 showed higher latency in both runs, likely from free-tier rate limiting
  (v4 always ran second); to be confirmed by reversing the run order.
- **Evidence:** `triage_20261118-195920.json`, `triage_20261118-200913.json`

### 2026-11-19 — Accept both values for `needs_human` on "paid service completely down"

- **Decision:** In the eval case `paid-service-completely-down`, `needs_human` accepts
  `true` or `false`.
- **Why:** Current rules don't clearly cover it (no money, security or legal issue; tone
  negative or angry). Marking either answer wrong would be unfair.
- **Open question for the customer:** Should a paying customer who cannot use the product
  at all always reach a human?
- **Revisit when:** The customer answers → add an explicit rule (v5) and tighten the case.

---

## Day 3 — 19–20 Nov 2026

### 2026-11-19 — Embedding model: FastEmbed with BAAI/bge-small-en-v1.5 (local)

- **Decision:** Local embeddings with FastEmbed (ONNX Runtime), `BAAI/bge-small-en-v1.5`
  (384 dimensions, English).
- **Why:** Free, no API key, no rate limits (we re-embed and re-run evals often), documents
  never leave the machine, no GPU needed.
- **Rejected:** Groq (no reliable embeddings endpoint); Voyage/Gemini free tiers (rate limits,
  external data transfer); OpenAI (paid).
- **Trade-offs:** English only; smaller than top API models.
- **Rule:** The same model embeds documents and queries; changing it means re-embedding everything.

### 2026-11-19 — PostgreSQL 18 + pgvector in Docker Compose, host port 5433

- **Decision:** `pgvector/pgvector:pg18` (pinned tag), named volume, `pg_isready` healthcheck,
  published on host port **5433**.
- **Why:** Matches common customer stacks; vectors next to metadata in one SQL query; same
  container locally and on AWS. Port 5433 because a local Windows PostgreSQL already uses 5432
  (clients silently connected to the wrong server).
- **Rejected:** A dedicated vector database (another product to operate); installing
  PostgreSQL directly on Windows (not reproducible).
- **Open item (Day 12):** The app connects as the `postgres` superuser — create a dedicated,
  limited DB user (least privilege).

### 2026-11-19 — SQL migrations with a small runner

- **Decision:** Numbered SQL files in `migrations/`, applied by `scripts/migrate.py`, tracked in
  `schema_migrations`, one transaction per migration.
- **Why:** Reproducible on any fresh database, history in Git, idempotent.
- **Rule:** Never edit an applied migration — add a new one (e.g. 004 for full-text search).
- **Production alternative:** Alembic.

### 2026-11-19 — `documents` table design

- **Decision:** `vector(384)`, JSONB `metadata`, unique `slug`, `timestamptz` timestamps.
- **Why JSONB:** Customer metadata varies; no schema change needed. **Trade-off:** less strict
  than real columns.
- **Indexes:** HNSW with `vector_cosine_ops` (must match the `<=>` operator, or the index is
  silently ignored) and GIN on `metadata`.

### 2026-11-20 — Embedding adapter and query prefix

- **Decision:** `app/embeddings.py` is the only module that knows the embedding library;
  `embed_passages()` for documents, `embed_query()` for queries with the BGE retrieval
  instruction from config (switchable via `EMBEDDING_USE_QUERY_PREFIX`).
- **Why:** Same model guaranteed for both; switching providers is a one-file change; the prefix
  addresses the query–document asymmetry seen in the playground.
- **Model cache** in the project's `.cache/fastembed` (git-ignored), not Windows Temp.

### 2026-11-20 — Idempotent ingestion

- **Decision:** Validate with Pydantic, reject duplicate slugs, embed `title + content`,
  upsert (`ON CONFLICT (slug) DO UPDATE`) in one transaction.
- **Why:** Safe to re-run; bad data never reaches the index; never half-updated.
- **Known cost:** Re-embeds every document each run → later: skip unchanged docs via content hash.

### 2026-11-20 — `/search` design

- **Decision:** `POST /search` (query, top_k 1–20, optional category, mode semantic|keyword);
  `score` field (similarity for semantic, `ts_rank_cd` for keyword — not comparable across modes);
  category filter as JSONB `@>` inside the same query; optional filters built from fixed SQL
  fragments with user values only as parameters; `ORDER BY embedding <=> …` so HNSW can be used.
- **Also:** Model warm-up at startup (FastAPI lifespan) — removes ~1 s cold start;
  DB unavailable → 503.
- **Known gaps:** New DB connection per search (~45 ms) → connection pool later.
- **API change:** `similarity` renamed to `score` (version 0.5.0) — breaking for clients.

### 2026-11-20 — Keyword search with OR, and default search mode

- **Decision:** Full-text search via migration 004 (generated `tsvector`, title weight A /
  content weight B, GIN index); keyword queries use **OR** (AND returns nothing for natural
  questions). Default mode: **semantic with query prefix**.
- **Evidence (10 queries, 20 docs, `search_20261119-203814.json`):**
  keyword Hit@1 80% / Hit@3 80% / MRR 0.80 — failed on "parcel never came" (no results) and
  "money back" (matched only "get"); semantic 100% / 100% / 1.00 with and without prefix.
- **Caveat:** Ceiling effect — the eval is too easy to separate the semantic variants.
- **Next:** Harder eval, hybrid search (combine by rank) and reranking (Day 4).
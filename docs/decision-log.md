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

## Day 4 — Fri 20 Nov 2026

### D4-1: Sentence-aligned chunking with overlap, two configs stored side by side
- **Decision:** Split documents into sentence-aligned chunks with overlap. Two configs:
  small (60 words / 15 overlap) and large (150 / 30), both stored in one `chunks`
  table with a `chunk_config` column. Embed "title + chunk" (contextual header).
- **Why:** Whole-document embeddings blur long guides; sentence alignment avoids cutting
  facts in half; overlap keeps facts that sit on a boundary; storing both configs lets
  us compare them with the same eval instead of guessing.
- **Rejected:** Fixed character windows (cut sentences); one config only (no comparison).

### D4-2: Hybrid search (RRF, k=60) + cross-encoder reranking
- **Decision:** Run semantic + keyword search, fuse with Reciprocal Rank Fusion (k=60),
  then rerank the top 20 candidates with a cross-encoder (ms-marco-MiniLM-L-6-v2).
- **Why:** Keyword search catches exact codes (e.g. "E-4012"); semantic search catches
  paraphrases; RRF combines ranks without tuning score scales; the cross-encoder reads
  query + chunk together and fixes ordering on hard cases.
- **Cost:** Retrieval ~106 ms → ~431 ms (reranker on CPU). Acceptable vs LLM time.

### D4-3: RAG answer contract enforced in code
- **Decision:** Prompt `rag_v1` + JSON output {answerable, answer}; exact IDK phrase when
  the context lacks the answer; citations `[slug#n]` extracted by regex and validated
  against retrieved source IDs; up to 3 attempts with feedback; empty context → IDK
  without calling the LLM; context deduped (>60% overlap) and capped at 700 words.
- **Why:** The prompt asks; the code verifies. Unverified citations look trustworthy
  but can be fake (confirmed in the LangChain demo: model cited a source it never got).

### D4-4: Defaults = hybrid + rerank + small chunks
- **Decision:** `rag_search_mode=hybrid`, `rag_rerank=True`, `default_chunk_config=small`.
- **Evidence:** RAG eval (rag_20261120-190729.json): semantic_small 10/10,
  hybrid_rerank_small 9/10 → 10/10 after scorer date-format fix (re-run: ?),
  hybrid_rerank_large 10/10 but ~25% more tokens (1012 vs 812) and slower LLM time.
- **Caveat:** Ceiling effect — all configs ≈ 10/10, so this eval cannot separate them.
  Hybrid + rerank chosen for robustness on exact codes and hard search cases
  (search eval: ?). Revisit when harder RAG cases exist.

### D4-5: Plain-Python RAG core; LangChain only as an adapter
- **Decision:** Keep retrieval, context, validation and evals in plain Python; expose
  search via a `BaseRetriever` adapter (`langchain-core` only).
- **Why:** Full control and testability; minimal dependencies; no framework schema
  lock-in. Demo showed a chain passing a hallucinated citation that /ask rejects.
- **Rejected:** Rebuilding on langchain-postgres PGVector (own tables; doesn't fit our
  chunks schema and migrations).

## Day 6 — Thu 26 / Fri 27 Nov 2026 (bug-fix agent, project day 1)

### D6-1: Project = bug-fix agent using official MCP servers
- **Decision:** Build a Python agent (MCP host + clients) that reads a Bug ticket from
  Azure Boards, finds related code in GitHub, shows a plan + diff for human approval,
  and only then opens a DRAFT pull request. Practice in our own repo (fde-sprint) with
  planted bugs; test tickets in a sandbox project (company organization, admin-approved).
- **Why:** Real team workflow (tickets in Azure Boards, code in GitHub); teaches MCP
  client side, agent design, safety, and evals.
- **Rejected:** Building custom MCP servers now (official servers exist and are maintained);
  Copilot coding agent integration (paid plans only).

### D6-2: Run both official servers locally over stdio
- **Decision:** GitHub MCP server via Docker (`ghcr.io/github/github-mcp-server`);
  Azure DevOps MCP server via `npx @azure-devops/mcp` with `-d core work-items`.
- **Why:** Local stdio works with our own Python client and a token; small tool lists.
- **Rejected:** Hosted Azure DevOps server (requires Microsoft Entra sign-in support
  in the client); hosted GitHub server (not needed yet).
- **Evidence:** Both connected in MCP Inspector; GitHub server negotiated MCP 2025-11-25.

### D6-3: Least-privilege tokens, 30-day expiry
- **Decision:** GitHub fine-grained token: only fde-sprint, Contents RW + Pull requests RW.
  Azure DevOps token: one organization, Work Items (Read) + Project and Team (Read) only.
  Secrets only in `.env` (git-ignored) and masked session variables; never in commands,
  code, logs, or chat.
- **Why:** If a token leaks or the LLM is tricked, the damage is limited by the platform.

### D6-4: "Never merge" and "never touch Azure Boards" enforced in layers
- **Decision:** Layer 1 — hide tools at the server (`GITHUB_EXCLUDE_TOOLS=merge_pull_request`,
  toolsets, read-only mode). Layer 2 — our own tool allowlist (Day 3). Layer 3 — platform
  permissions (read-only Azure DevOps token; branch protection on main, later).
- **Why:** A prompt saying "don't merge" is not a control; code and permissions are.
- **Evidence:** Excluding merge_pull_request: 29 → 28 tools. Adding a comment with the
  Azure DevOps token: "Unauthorized".

### D6-5: Don't rely on GitHub code search; browse folders instead
- **Decision:** Locate code by listing folders (`get_file_contents` on `app/`) and reading
  candidate files; add local search later.
- **Why:** `search_code` returned 0 results (`incomplete_results: true`) for two terms that
  exist in app/rag.py. Folder listing worked (18 files, with size + sha).
- **Rejected:** search_code as the main locating step (unreliable for this repo).

### D6-6: Clean and minimize ticket data before the LLM sees it
- **Decision:** Extract only title, type, state, priority, severity, repro steps, comments,
  link. Convert Repro Steps from HTML to plain text. Keep the server's untrusted-content
  markers and add our own delimiters.
- **Why:** Responses include names, emails and identity IDs the LLM doesn't need (privacy
  and tokens); ticket text is untrusted input (prompt injection).

### D6-7: Free LLMs only
- **Decision:** Groq `openai/gpt-oss-120b` (free tier) as the main model; a local Ollama
  model for comparison on eval day. No free tier that uses data for training on company code.
- **Why:** Zero cost for the experiment; Groq's 8K tokens/minute limit means sending
  only relevant code snippets.
- **Evidence:** try_llm: 200 OK, 99/120 tokens, ~967 ms.

## Day 7 — Fri 27 Nov 2026 (bug-fix agent, project day 2)

### D7-1: Unit tests are the judge of a fix
- **Decision:** pytest unit tests for pure functions (no DB, no LLM, no network).
  30 tests on main, all passing. A fix is correct only if its failing tests pass and
  no other test breaks.
- **Why:** Deterministic, fast, objective scoring — the agent can verify itself later.

### D7-2: Planted bugs live on a separate branch
- **Decision:** `bug-playground` branch with 6 planted bugs (8 failing tests); agent PRs
  target this branch; main stays correct.
- **Why:** Realistic practice without ever breaking the working app.

### D7-3: No answer key visible to the agent
- **Decision:** Bugs committed together with a neutral message; agent will not be allowed
  commit-history tools (get_commit, list_commits, search_commits); the answer key
  (`evals/bugfix_cases.json`) exists only on main, not on bug-playground.
- **Why:** Otherwise the eval measures reading git history, not fixing bugs.

### D7-4: Tickets describe symptoms, not fixes
- **Decision:** 6 Bug tickets written like QA reports (repro steps, expected vs actual,
  impact), no file names or solutions.
- **Why:** Finding the right code is part of what we want to measure.

### D7-5: requirements.txt saved as plain ASCII
- **Decision:** `pip freeze | Set-Content -Encoding ascii requirements.txt`
- **Why:** PowerShell `>` wrote UTF-16, which GitHub shows garbled.

## Day 8 — Sat 28 Nov 2026 (bug-fix agent, project day 3)

### D8-1: MCP Python SDK v2 `Client`, pinned to 2.x
- **Decision:** `mcp>=2,<3`; one `Client(StdioServerParameters(...))` per server.
- **Why:** Current stable line; v2 replaces v1's transport + ClientSession + initialize.
- **Evidence:** GitHub server negotiated 2026-07-28; Azure DevOps server fell back to
  2025-11-25 automatically.

### D8-2: Each server only gets its own secret
- **Decision:** Pass tokens through `env=`; the SDK starts servers with an allow-listed
  environment, so the GitHub server never sees the Azure DevOps token (and vice versa).

### D8-3: Minimal, clean ticket data
- **Decision:** Request only 7 fields (`fields` argument), unwrap the server's untrusted
  markers, convert Repro Steps HTML to text, parse into a frozen `BugTicket`; non-Bugs rejected.
- **Why:** No names/emails ever reach the agent; fewer tokens; predictable input.

### D8-4: Safety layer 2 — deny-by-default tool policy
- **Decision:** 5 allowed tools (1 Azure DevOps read, 1 GitHub read, 3 GitHub writes).
  Azure DevOps actions limited to get/list_comments. Our repo only. Writes need approval,
  branches `bugfix/*` from bug-playground, draft PRs into bug-playground only.
  Only `app/` may change — never `tests/` (the tests are the judge).
- **Evidence:** 20 policy tests; live smoke test blocked 5 forbidden calls before any
  message reached a server.

### D8-5: One hub, least privilege per phase
- **Decision:** `McpHub` starts both servers (AsyncExitStack), shows the LLM only allowed
  tools, policy-checks every call, logs metadata only. GitHub server is read-only in the
  plan phase; pull-request tools only after approval; merge always excluded.

### D8-6: Handle embedded resources in tool results
- **Decision:** Read text from `TextContent` and `EmbeddedResource` (text resources).
- **Why:** get_file_contents returns the file as an EmbeddedResource; reading only
  TextContent silently dropped the file.
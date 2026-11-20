# Day 3 — Thu 19 Nov 2026 (finished Fri 20 Nov)

**Focus:** Embeddings and vector databases + Demo 1
**Status:** 🟡 Amber — Day 3 complete one day late; no blockers; plan to catch up during Day 4–5.

---

## What I built

- **Embedding playground** (`scripts/embedding_playground.py`): vectors, cosine vs dot product,
  ranking, failure cases
- **PostgreSQL 18 + pgvector** in Docker Compose (pinned image, named volume, healthcheck,
  host port 5433)
- **SQL migrations** (`migrations/001–004`) + runner (`scripts/migrate.py`, `schema_migrations`)
- **Knowledge base**: 20 help-centre articles (`data/knowledge_base.json`)
- **`documents` table**: `vector(384)`, JSONB metadata, unique slug, HNSW + GIN indexes,
  generated `tsvector` column for keyword search
- **Embedding adapter** (`app/embeddings.py`), **DB helper** (`app/db.py`)
- **Idempotent ingestion** (`scripts/ingest.py`): validate → embed → upsert in one transaction
- **`POST /search`**: semantic and keyword modes, category filter, stage timings,
  model warm-up at startup, 503 when the DB is down
- **Search eval** (`evals/search_cases.json`, `scripts/run_search_eval.py`): Hit@1, Hit@3, MRR
- **Demo 1** script, status, README update

---

## What broke and how I fixed it

1. **Docker "failed to connect to the docker API"**
   - Cause: Docker Desktop's engine hadn't finished starting. Fix: wait for "Engine running".

2. **`role "fde" does not exist`**
   - Cause: my `.env` had `POSTGRES_USER=postgres`; the guide's command used `fde`.
   - Found with `docker compose config` (shows values after variable substitution).
   - Lesson: DB containers apply user/password/db **only on the first start with an empty volume**;
     changing them later needs `docker compose down -v`.
   - Lesson: "healthy" (`pg_isready`) ≠ correctly configured.

3. **Python connected to the wrong PostgreSQL**
   - `db_check` showed `18.6 on x86_64-windows, msvc` instead of `18.7 Debian linux`.
   - Cause: a locally installed Windows PostgreSQL (process `postgres`, PID 4156) was already
     listening on port 5432.
   - Fix: Docker DB moved to host port **5433** (`"5433:5432"`), `DATABASE_URL` updated.
   - Second cause along the way: `.env` still had 5432 (found with a `urlparse` one-liner that
     prints host/port without the password; `Test-Path Env:DATABASE_URL` ruled out an override).
   - Lesson: verification checks pay off — print **where** you're connecting, not just success.

4. **`\d documents` printed nothing** → psql pager; fixed with `\pset pager off`.

5. **Security:** pasted a DB password that may be reused elsewhere → switched to a local-only
   dev password. Lesson: never reuse real passwords; check output for secrets before pasting.

6. **Model cached in Windows Temp** → moved to project `.cache/fastembed` (git-ignored).

---

## What I learned

### Embeddings
- An embedding is a list of numbers representing meaning; similar meaning → nearby vectors,
  even with no shared words.
- **Cosine similarity** (angle) vs **dot product**; for **normalized** vectors they're equal —
  verified (norm = 1.0000, identical columns).
- Dimensions (384) must match the model **and** the DB column; same model for docs and queries.
- **Limits:** weak on negation ("I do not want a refund" ranked #2 for a refund question);
  captures phrasing/form (query–document asymmetry) → BGE query instruction prefix.
- Scores are compressed and setup-dependent (0.79 in playground vs 0.67 in the API) →
  rank, don't threshold.
- Local embeddings: free, fast (~15 ms), no rate limits, data stays local.

### Vector databases (PostgreSQL + pgvector)
- `CREATE EXTENSION vector`; `vector(n)` column; operators `<=>` cosine, `<->` L2, `<#>` neg. inner.
- Cosine **distance** = 1 − similarity → `ORDER BY` ascending; top-k = `LIMIT k`.
- **HNSW** = graph-based approximate nearest-neighbour index; **operator class must match**
  the query operator (`vector_cosine_ops` ↔ `<=>`) or it's silently ignored.
- Small tables use a sequential scan anyway (`EXPLAIN` shows the plan).
- **JSONB** metadata + GIN index; `->>` reads a key, `@>` "contains" filter.
- Filter **during** the search (same query), not after.

### Docker
- Image / container / volume / port mapping / Compose; `up -d`, `ps`, `logs`, `exec`, `down`, `down -v`.
- Pin image tags; healthchecks; `docker compose config` to debug variables.
- Two services on one port: the client connects to whichever answers.

### Migrations and data
- Numbered SQL files, applied once each, tracked in a table, one transaction per migration.
- Never edit an applied migration — add a new one (004 added full-text search).
- Idempotency: running again changes nothing.
- **Ingestion pipeline:** load → validate (Pydantic) → embed in one batch → upsert in one
  transaction (`ON CONFLICT … DO UPDATE`, `EXCLUDED`).
- Validate data files at the edge, like HTTP input.
- Query parameters prevent **SQL injection**; optional filters from fixed SQL fragments only.

### Search and retrieval evaluation
- **Keyword (full-text):** tsvector/tsquery, stemming, stop words, weights (title A, content B),
  `ts_rank_cd`; great for exact codes; fails without shared words; AND vs OR matters.
- **Semantic:** matches meaning; weaker on exact codes at scale and negation.
- **Metrics:** Hit@1, Hit@3 (recall@3), MRR.
- **Ceiling effect:** when everything scores 100%, the eval is too easy to compare.
- Scores from different methods aren't comparable → combine by **rank** (hybrid, Day 4).

### Python
- numpy (`np.dot`, `np.linalg.norm`), `zip`, `enumerate`, `next(iter(...))`
- `@contextmanager` / `@asynccontextmanager` + `yield` (own `with` blocks; FastAPI lifespan)
- Set comprehensions, one-item tuples `(x,)`, `**options` into function calls
- `Path` fields in settings, `.glob()` + `sorted`, `urlparse`
- Overridable defaults (`use_prefix: bool | None = None`)

### Engineering / FDE practice
- Cold start → warm up models at startup (measured ~1 s → ~15 ms).
- Per-stage timing (`embedding_ms` vs `db_ms`) shows where time goes (connection ≈ 45 ms).
- Breaking API change (`similarity` → `score`) → version bump.
- Demo in plain language: problem → live proof → evidence → cost/risk/limits → status → next.

---

## Checklist status (from the plan)

- [x] Embedding model chosen and noted
- [x] Docs embedded and stored (20)
- [x] Search endpoint returns top-k
- [x] pgvector table and index created
- [x] Keyword vs semantic comparison done
- [x] Demo prepared (recording: ?)
- [x] Status (G/A/R) recorded — Amber

---

## Measurements

### Embedding playground (query: "How do I get my money back?")

| Rank | Document | Cosine |
|---|---|---|
| 1 | What is your refund policy? | 0.792 |
| 2 | I do not want a refund. ← negation trap | 0.756 |
| 3 | How do I reset my password? ← same question form | 0.606 |
| 4 | Returns are accepted within 14 days of delivery. | 0.569 |
| 5 | My package hasn't arrived yet. | 0.550 |
| 6 | The cat sat on the mat. | 0.387 |

384 dims, norm 1.0000, cosine = dot; 6 docs embedded in 27 ms; model 67.2 MB (quantized).

### /search (semantic, "How do I get my money back?", top 3)

refund-policy 0.673 · refund-sale-items 0.665 · suspicious-activity 0.622
embedding_ms 16.5 · db_ms 45.5

### Search eval — 10 queries, top_k 5 (`search_20261119-203814.json`)

| Config | Hit@1 | Hit@3 | MRR@5 |
|---|---|---|---|
| keyword | 80% | 80% | 0.80 |
| semantic_no_prefix | 100% | 100% | 1.00 |
| semantic_prefix | 100% | 100% | 1.00 |

Keyword failures: `money-back` (returned contact-support, matched only "get"),
`parcel-never-came` (no results).

---

## Evidence

- Commit links: ?
- `evals/results/search_20261119-203814.json`
- Demo recording: ?
- `progress.md` (status sheet), `docs/decision-log.md` (Day 3 entries)

---

## Open items

- Harder search eval (more documents, near-duplicates, similar error codes)
- Connection pool for the database
- Dedicated limited DB user (Day 12)
- Skip re-embedding unchanged documents (content hash)
- Day 2 leftovers to record in day-02.md: `/assistant` test results, streaming numbers

---

## Next — Day 4 (planned Fri 20 Nov)

- Full RAG loop: chunking (2–3 sizes and overlaps), retrieval, optional reranking
- Context engineering: ordering, trimming, deduplicating, labelling chunks
- Answers **with citations**, and "I don't know" when the context is missing
- 10 test questions with expected sources; compare keyword / vector / **hybrid**,
  with and without a reranker; score retrieval relevance and answer grounding
- Teach-back: LangChain retrievers and runnables vs plain Python
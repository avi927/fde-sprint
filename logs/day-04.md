# Day 4 — Chunking, hybrid search, reranking, RAG and evals
**Date:** Fri 20 Nov 2026 (teach-back Sat 21 Nov)  **Status:** ?

## Goal
Turn search into a grounded question-answering endpoint (/ask) that answers only
from our help articles, cites sources, and says "I don't know" when it should —
and prove it with an eval.

## What I built
- `app/chunking.py` — sentence-aligned chunks with overlap; configs small (60/15), large (150/30)
- `migrations/005_create_chunks_table.sql` — chunks table (FK + CASCADE, HNSW, GIN, chunk_config)
- `scripts/ingest.py` (chunked) — 23 documents → 34 small + 26 large chunks, one transaction
- Knowledge base extended with 3 long guides (returns, shipping, account security)
- `app/reranking.py` — cross-encoder reranker (ms-marco-MiniLM-L-6-v2)
- `app/search.py` — semantic / keyword / hybrid (RRF k=60) + optional rerank over chunks
- `app/context.py` — dedupe, 700-word budget, <source id> labels, sanitizing
- `app/rag.py` + `prompts/rag_v1.md` — RAG with citation validation, IDK contract, retries
- `POST /ask` (API v0.8.0)
- `scripts/run_search_eval.py` (5 strategies, 16 queries), `scripts/run_rag_eval.py` (3 configs, 10 cases)
- `scripts/langchain_teachback.py` + `docs/teachback-langchain.md`

## Concepts I learned
- Chunking: why whole-document embeddings blur facts; chunk size vs overlap trade-off
- Contextual chunk header (title + chunk) for better embeddings
- Hybrid search; Reciprocal Rank Fusion; two-stage retrieval (retrieve wide, rerank narrow)
- Bi-encoder (embeddings) vs cross-encoder (reranker)
- Context engineering: ordering, dedupe, budget, source labels, "lost in the middle"
- Grounding: prompt asks, code verifies (citations checked against retrieved IDs)
- RAG eval: retrieval vs answer scoring, hallucination / false IDK diagnosis, ceiling effect
- LangChain: runnables, `|` composition, retrievers; framework = plumbing, not quality

## Results
| Eval | Result |
|---|---|
| Search eval (16 queries) | ? (Hit@1 / Hit@3 / MRR per strategy) |
| RAG semantic_small | 10/10, ~808 tokens, retrieval 106 ms, LLM 785 ms |
| RAG hybrid_rerank_small | 9/10 → ? after scorer fix; ~812 tokens, retrieval 431 ms |
| RAG hybrid_rerank_large | 10/10, ~1012 tokens, retrieval 776 ms, LLM 2595 ms |
| Before/after | /chat invented "30 days" (Day 2); /ask answers "14 days" with a citation |

## Errors and fixes
| Error | Cause | Fix / lesson |
|---|---|---|
| 86 MB + 67 MB model files pushed | `.gitignore` had `cache/` not `.cache/` | Fixed pattern; `git rm -r --cached .cache`; check `git status` before every add |
| `/openapi.json` 500, ForwardRef('AskResponse') | Ask* schemas not imported in main.py (Python 3.14 lazy annotations) | Import them; run the `app.openapi()` pre-flight check |
| `'NoneType' object has no attribute 'sources'` | Partial edit deleted the body of `answer_question` → implicit `return None` | Replace whole functions, not fragments |
| holiday-deadline "wrong_answer" | Scorer required one exact date format | Scorer accepts alternatives (`a|b|c`) — "test the test" |

## Key insight
?  (one or two sentences in your own words)

## Open items
- Optional: remove model files from git history (filter-repo)
- Harder RAG eval cases (break the ceiling effect)
- Backlog: connection pool, content-hash re-embedding skip, LLM-as-judge grounding


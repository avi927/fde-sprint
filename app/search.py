"""Search over knowledge base chunks: semantic, keyword or hybrid, with optional reranking."""

import logging
import time
from dataclasses import dataclass, replace
from typing import Any, Literal

from psycopg.types.json import Jsonb

from app.chunking import chunk_embedding_text
from app.config import get_settings
from app.db import get_connection
from app.embeddings import embed_query
from app.reranking import score_pairs

logger = logging.getLogger(__name__)

SearchMode = Literal["semantic", "keyword", "hybrid"]

SEMANTIC_SQL = """
SELECT c.id,
       d.slug,
       d.title,
       d.metadata->>'category' AS category,
       c.chunk_index,
       c.content,
       1 - (c.embedding <=> %(query_vector)s) AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE c.chunk_config = %(chunk_config)s
{category_clause}
ORDER BY c.embedding <=> %(query_vector)s
LIMIT %(limit)s
"""

KEYWORD_SQL = """
WITH q AS (
    SELECT replace(
               websearch_to_tsquery('english', %(query_text)s)::text, '&', '|'
           )::tsquery AS query
)
SELECT c.id,
       d.slug,
       d.title,
       d.metadata->>'category' AS category,
       c.chunk_index,
       c.content,
       ts_rank_cd(c.search_tsv, q.query) AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
CROSS JOIN q
WHERE c.chunk_config = %(chunk_config)s
  AND c.search_tsv @@ q.query
{category_clause}
ORDER BY score DESC
LIMIT %(limit)s
"""


@dataclass(frozen=True)
class ChunkHit:
    """One search result: a chunk of a document (internal shape)."""

    chunk_id: int
    slug: str
    title: str
    category: str
    chunk_index: int
    content: str
    score: float

    @property
    def source_id(self) -> str:
        """Readable citation ID, e.g. 'returns-guide#2'."""
        return f"{self.slug}#{self.chunk_index}"


@dataclass(frozen=True)
class SearchOutcome:
    """The results plus what was searched and how long each stage took."""

    hits: list[ChunkHit]
    mode: str
    chunk_config: str
    reranked: bool
    embedding_ms: float
    db_ms: float
    rerank_ms: float


def _fetch(
    mode: Literal["semantic", "keyword"],
    query: str,
    limit: int,
    category: str | None,
    chunk_config: str,
    use_prefix: bool | None,
) -> tuple[list[ChunkHit], float, float]:
    """Run one retrieval query. Returns (hits, embedding_ms, db_ms)."""
    params: dict[str, Any] = {"limit": limit, "chunk_config": chunk_config}

    category_clause = ""
    if category is not None:
        params["category_filter"] = Jsonb({"category": category})
        category_clause = "AND d.metadata @> %(category_filter)s"

    embedding_ms = 0.0
    if mode == "semantic":
        start = time.perf_counter()
        params["query_vector"] = embed_query(query, use_prefix=use_prefix)
        embedding_ms = (time.perf_counter() - start) * 1000
        sql = SEMANTIC_SQL.format(category_clause=category_clause)
    else:
        params["query_text"] = query
        sql = KEYWORD_SQL.format(category_clause=category_clause)

    start = time.perf_counter()
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    db_ms = (time.perf_counter() - start) * 1000

    hits = [
        ChunkHit(
            chunk_id=row[0],
            slug=row[1],
            title=row[2],
            category=row[3],
            chunk_index=row[4],
            content=row[5],
            score=round(float(row[6]), 4),
        )
        for row in rows
    ]
    return hits, embedding_ms, db_ms


def reciprocal_rank_fusion(result_lists: list[list[ChunkHit]], k: int = 60) -> list[ChunkHit]:
    """Merge ranked lists by rank, not by score: score = sum of 1 / (k + rank)."""
    fused_scores: dict[int, float] = {}
    hits_by_id: dict[int, ChunkHit] = {}

    for hits in result_lists:
        for rank, hit in enumerate(hits, start=1):
            fused_scores[hit.chunk_id] = fused_scores.get(hit.chunk_id, 0.0) + 1 / (k + rank)
            hits_by_id.setdefault(hit.chunk_id, hit)

    ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)
    return [replace(hits_by_id[cid], score=round(fused_scores[cid], 6)) for cid in ranked_ids]


def _rerank(query: str, hits: list[ChunkHit]) -> list[ChunkHit]:
    """Re-score candidates with the cross-encoder and sort by the new score."""
    passages = [chunk_embedding_text(hit.title, hit.content) for hit in hits]
    scores = score_pairs(query, passages)
    rescored = [replace(hit, score=round(score, 4)) for hit, score in zip(hits, scores)]
    return sorted(rescored, key=lambda hit: hit.score, reverse=True)


def search_chunks(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    mode: SearchMode = "semantic",
    use_prefix: bool | None = None,
    chunk_config: str | None = None,
    rerank: bool = False,
) -> SearchOutcome:
    """Two-stage retrieval: fetch candidates (semantic, keyword or hybrid), optionally rerank."""
    settings = get_settings()
    chunk_config = chunk_config or settings.default_chunk_config

    # Stage 1 fetches more candidates when something will re-order them afterwards.
    needs_candidates = rerank or mode == "hybrid"
    limit = max(top_k, settings.rerank_candidates) if needs_candidates else top_k

    # Stage 1: retrieval
    if mode == "hybrid":
        semantic_hits, embedding_ms, db_ms_1 = _fetch(
            "semantic", query, limit, category, chunk_config, use_prefix
        )
        keyword_hits, _, db_ms_2 = _fetch(
            "keyword", query, limit, category, chunk_config, use_prefix
        )
        hits = reciprocal_rank_fusion([semantic_hits, keyword_hits], k=settings.rrf_k)
        db_ms = db_ms_1 + db_ms_2
    else:
        hits, embedding_ms, db_ms = _fetch(
            mode, query, limit, category, chunk_config, use_prefix
        )

    # Stage 2: reranking (optional)
    rerank_ms = 0.0
    if rerank and hits:
        start = time.perf_counter()
        hits = _rerank(query, hits)
        rerank_ms = (time.perf_counter() - start) * 1000

    hits = hits[:top_k]

    logger.info(
        "search_completed",
        extra={
            "extra_fields": {
                "mode": mode,
                "reranked": rerank,
                "chunk_config": chunk_config,
                "top_k": top_k,
                "candidates": limit,
                "category": category,
                "results": len(hits),
                "embedding_ms": round(embedding_ms, 1),
                "db_ms": round(db_ms, 1),
                "rerank_ms": round(rerank_ms, 1),
            }
        },
    )
    return SearchOutcome(
        hits=hits,
        mode=mode,
        chunk_config=chunk_config,
        reranked=rerank,
        embedding_ms=round(embedding_ms, 1),
        db_ms=round(db_ms, 1),
        rerank_ms=round(rerank_ms, 1),
    )
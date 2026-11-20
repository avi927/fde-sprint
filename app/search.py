"""Search over knowledge base chunks: semantic (vectors) or keyword (full-text)."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from psycopg.types.json import Jsonb

from app.config import get_settings
from app.db import get_connection
from app.embeddings import embed_query

logger = logging.getLogger(__name__)

SearchMode = Literal["semantic", "keyword"]

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
LIMIT %(top_k)s
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
LIMIT %(top_k)s
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
    """The results, which chunk config was searched, and how long each stage took."""

    hits: list[ChunkHit]
    chunk_config: str
    embedding_ms: float
    db_ms: float


def search_chunks(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    mode: SearchMode = "semantic",
    use_prefix: bool | None = None,
    chunk_config: str | None = None,
) -> SearchOutcome:
    """Return the top_k most relevant chunks, by meaning (semantic) or by words (keyword)."""
    chunk_config = chunk_config or get_settings().default_chunk_config
    params: dict[str, Any] = {"top_k": top_k, "chunk_config": chunk_config}

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

    logger.info(
        "search_completed",
        extra={
            "extra_fields": {
                "mode": mode,
                "chunk_config": chunk_config,
                "top_k": top_k,
                "category": category,
                "results": len(hits),
                "top_score": hits[0].score if hits else None,
                "embedding_ms": round(embedding_ms, 1),
                "db_ms": round(db_ms, 1),
            }
        },
    )
    return SearchOutcome(
        hits=hits,
        chunk_config=chunk_config,
        embedding_ms=round(embedding_ms, 1),
        db_ms=round(db_ms, 1),
    )
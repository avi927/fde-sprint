"""Search over the knowledge base: semantic (vectors) or keyword (full-text)."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from psycopg.types.json import Jsonb

from app.db import get_connection
from app.embeddings import embed_query

logger = logging.getLogger(__name__)

SearchMode = Literal["semantic", "keyword"]

SEMANTIC_SQL = """
SELECT slug,
       title,
       content,
       metadata->>'category' AS category,
       1 - (embedding <=> %(query_vector)s) AS score
FROM documents
{where_clause}
ORDER BY embedding <=> %(query_vector)s
LIMIT %(top_k)s
"""

KEYWORD_SQL = """
WITH q AS (
    SELECT replace(
               websearch_to_tsquery('english', %(query_text)s)::text, '&', '|'
           )::tsquery AS query
)
SELECT slug,
       title,
       content,
       metadata->>'category' AS category,
       ts_rank_cd(search_tsv, q.query) AS score
FROM documents, q
WHERE search_tsv @@ q.query
{and_clause}
ORDER BY score DESC
LIMIT %(top_k)s
"""


@dataclass(frozen=True)
class DocumentHit:
    """One search result (internal shape)."""

    slug: str
    title: str
    content: str
    category: str
    score: float


@dataclass(frozen=True)
class SearchOutcome:
    """The results plus how long each stage took."""

    hits: list[DocumentHit]
    embedding_ms: float
    db_ms: float


def _category_condition(category: str | None, params: dict[str, Any]) -> str:
    """Return a fixed SQL condition for the category filter (value goes in params)."""
    if category is None:
        return ""
    params["category_filter"] = Jsonb({"category": category})
    return "metadata @> %(category_filter)s"


def search_documents(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    mode: SearchMode = "semantic",
    use_prefix: bool | None = None,
) -> SearchOutcome:
    """Return the top_k most relevant documents, by meaning (semantic) or by words (keyword)."""
    params: dict[str, Any] = {"top_k": top_k}
    condition = _category_condition(category, params)
    embedding_ms = 0.0

    if mode == "semantic":
        start = time.perf_counter()
        params["query_vector"] = embed_query(query, use_prefix=use_prefix)
        embedding_ms = (time.perf_counter() - start) * 1000
        sql = SEMANTIC_SQL.format(
            where_clause=f"WHERE {condition}" if condition else ""
        )
    else:
        params["query_text"] = query
        sql = KEYWORD_SQL.format(and_clause=f"AND {condition}" if condition else "")

    start = time.perf_counter()
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    db_ms = (time.perf_counter() - start) * 1000

    hits = [
        DocumentHit(
            slug=row[0],
            title=row[1],
            content=row[2],
            category=row[3],
            score=round(float(row[4]), 4),
        )
        for row in rows
    ]

    logger.info(
        "search_completed",
        extra={
            "extra_fields": {
                "mode": mode,
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
        hits=hits, embedding_ms=round(embedding_ms, 1), db_ms=round(db_ms, 1)
    )
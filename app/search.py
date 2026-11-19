"""Semantic search over the knowledge base: embed the query, find the nearest documents."""

import logging
import time
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from app.db import get_connection
from app.embeddings import embed_query

logger = logging.getLogger(__name__)

SEARCH_SQL = """
SELECT slug,
       title,
       content,
       metadata->>'category' AS category,
       1 - (embedding <=> %(query_vector)s) AS similarity
FROM documents
{where_clause}
ORDER BY embedding <=> %(query_vector)s
LIMIT %(top_k)s
"""


@dataclass(frozen=True)
class DocumentHit:
    """One search result (internal shape)."""

    slug: str
    title: str
    content: str
    category: str
    similarity: float


@dataclass(frozen=True)
class SearchOutcome:
    """The results plus how long each stage took."""

    hits: list[DocumentHit]
    embedding_ms: float
    db_ms: float


def search_documents(
    query: str, top_k: int = 5, category: str | None = None
) -> SearchOutcome:
    """Return the top_k documents most similar to the query, optionally in one category."""
    # 1. Embed the query (with the retrieval instruction)
    start = time.perf_counter()
    query_vector = embed_query(query)
    embedding_ms = (time.perf_counter() - start) * 1000

    # 2. Build the SQL: fixed text from us, user values only as parameters
    params: dict[str, Any] = {"query_vector": query_vector, "top_k": top_k}
    where_clause = ""
    if category is not None:
        where_clause = "WHERE metadata @> %(category_filter)s"
        params["category_filter"] = Jsonb({"category": category})
    sql = SEARCH_SQL.format(where_clause=where_clause)

    # 3. Run the nearest-neighbour query
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
            similarity=round(float(row[4]), 4),
        )
        for row in rows
    ]

    logger.info(
        "search_completed",
        extra={
            "extra_fields": {
                "top_k": top_k,
                "category": category,
                "results": len(hits),
                "top_similarity": hits[0].similarity if hits else None,
                "embedding_ms": round(embedding_ms, 1),
                "db_ms": round(db_ms, 1),
            }
        },
    )
    return SearchOutcome(
        hits=hits, embedding_ms=round(embedding_ms, 1), db_ms=round(db_ms, 1)
    )
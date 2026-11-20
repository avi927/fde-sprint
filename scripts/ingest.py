"""Ingest the knowledge base: upsert documents, then chunk + embed them for every chunk config."""

import json
import time
from datetime import date
from pathlib import Path
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.chunking import CHUNK_CONFIGS, Chunk, chunk_embedding_text, chunk_text
from app.db import get_connection
from app.embeddings import embed_passages
from app.logging_config import setup_logging

ROOT = Path(__file__).resolve().parent.parent
KB_FILE = ROOT / "data" / "knowledge_base.json"

UPSERT_DOCUMENT_SQL = """
INSERT INTO documents (slug, title, content, metadata, embedding)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (slug) DO UPDATE SET
    title      = EXCLUDED.title,
    content    = EXCLUDED.content,
    metadata   = EXCLUDED.metadata,
    embedding  = EXCLUDED.embedding,
    updated_at = now()
RETURNING id
"""

DELETE_CHUNKS_SQL = "DELETE FROM chunks WHERE document_id = %s AND chunk_config = %s"

INSERT_CHUNK_SQL = """
INSERT INTO chunks (document_id, chunk_config, chunk_index, content, word_count, embedding)
VALUES (%s, %s, %s, %s, %s, %s)
"""


class KBDocument(BaseModel):
    """One knowledge base article, validated before it touches the database."""

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1)
    category: Literal["billing", "shipping", "technical", "account", "other"]
    updated_at: date
    content: str = Field(min_length=1)


def load_documents() -> list[KBDocument]:
    """Read and validate the knowledge base file; reject duplicate slugs."""
    raw_items = json.loads(KB_FILE.read_text(encoding="utf-8"))
    docs = [KBDocument.model_validate(item) for item in raw_items]
    slugs = [doc.slug for doc in docs]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("Duplicate slugs found in the knowledge base file")
    return docs


def plan_chunks(docs: list[KBDocument], max_words: int, overlap_words: int) -> list[tuple[KBDocument, Chunk]]:
    """Chunk every document; return (document, chunk) pairs in order."""
    return [
        (doc, chunk)
        for doc in docs
        for chunk in chunk_text(doc.content, max_words, overlap_words)
    ]


def main() -> None:
    setup_logging("WARNING")
    docs = load_documents()
    print(f"Loaded and validated {len(docs)} documents")

    # 1. Slow work first (no database transaction open yet): embeddings.
    start = time.perf_counter()
    doc_vectors = embed_passages([chunk_embedding_text(doc.title, doc.content) for doc in docs])

    planned: dict[str, list[tuple[KBDocument, Chunk]]] = {}
    chunk_vectors: dict[str, list] = {}
    for config in CHUNK_CONFIGS.values():
        pairs = plan_chunks(docs, config.max_words, config.overlap_words)
        planned[config.name] = pairs
        chunk_vectors[config.name] = embed_passages(
            [chunk_embedding_text(doc.title, chunk.text) for doc, chunk in pairs]
        )
    print(f"Embedded documents and chunks in {(time.perf_counter() - start) * 1000:.0f} ms")

    # 2. Fast work inside one transaction: write everything.
    with get_connection() as conn:
        with conn.cursor() as cur:
            doc_ids: dict[str, int] = {}
            for doc, vector in zip(docs, doc_vectors):
                metadata = Jsonb(
                    {
                        "category": doc.category,
                        "updated_at": doc.updated_at.isoformat(),
                        "source": "help-center",
                    }
                )
                cur.execute(
                    UPSERT_DOCUMENT_SQL,
                    (doc.slug, doc.title, doc.content, metadata, vector),
                )
                doc_ids[doc.slug] = cur.fetchone()[0]

            for config in CHUNK_CONFIGS.values():
                for doc in docs:
                    cur.execute(DELETE_CHUNKS_SQL, (doc_ids[doc.slug], config.name))
                cur.executemany(
                    INSERT_CHUNK_SQL,
                    [
                        (
                            doc_ids[doc.slug],
                            config.name,
                            chunk.index,
                            chunk.text,
                            chunk.word_count,
                            vector,
                        )
                        for (doc, chunk), vector in zip(
                            planned[config.name], chunk_vectors[config.name]
                        )
                    ],
                )

        counts = conn.execute(
            "SELECT chunk_config, count(*) FROM chunks GROUP BY chunk_config ORDER BY chunk_config"
        ).fetchall()

    print(f"Documents in database: {len(doc_ids)}")
    for config_name, count in counts:
        print(f"Chunks [{config_name}]: {count}")


if __name__ == "__main__":
    main()
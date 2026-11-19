"""Load the knowledge base, embed every document, and upsert it into PostgreSQL."""

import json
import time
from datetime import date
from pathlib import Path
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.db import get_connection
from app.embeddings import embed_passages
from app.logging_config import setup_logging

ROOT = Path(__file__).resolve().parent.parent
KB_FILE = ROOT / "data" / "knowledge_base.json"

UPSERT_SQL = """
INSERT INTO documents (slug, title, content, metadata, embedding)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (slug) DO UPDATE SET
    title      = EXCLUDED.title,
    content    = EXCLUDED.content,
    metadata   = EXCLUDED.metadata,
    embedding  = EXCLUDED.embedding,
    updated_at = now()
"""


class KBDocument(BaseModel):
    """One knowledge base article, validated before it touches the database."""

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1)
    category: Literal["billing", "shipping", "technical", "account", "other"]
    updated_at: date
    content: str = Field(min_length=1)


def embedding_text(doc: KBDocument) -> str:
    """The text we embed: title + content (the title carries strong topic signal)."""
    return f"{doc.title}\n\n{doc.content}"


def main() -> None:
    setup_logging("WARNING")

    # 1. Load and validate
    raw_items = json.loads(KB_FILE.read_text(encoding="utf-8"))
    docs = [KBDocument.model_validate(item) for item in raw_items]

    slugs = [doc.slug for doc in docs]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("Duplicate slugs found in the knowledge base file")
    print(f"Loaded and validated {len(docs)} documents from {KB_FILE.relative_to(ROOT)}")

    # 2 + 3. Build texts and embed them in one batch
    start = time.perf_counter()
    vectors = embed_passages([embedding_text(doc) for doc in docs])
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"Embedded {len(vectors)} documents in {elapsed_ms:.0f} ms")

    # 4. Upsert everything in one transaction
    rows = [
        (
            doc.slug,
            doc.title,
            doc.content,
            Jsonb(
                {
                    "category": doc.category,
                    "updated_at": doc.updated_at.isoformat(),
                    "source": "help-center",
                }
            ),
            vector,
        )
        for doc, vector in zip(docs, vectors)
    ]

    with get_connection() as conn:
        before = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
        after = conn.execute("SELECT count(*) FROM documents").fetchone()[0]

    print(f"Documents in database: {before} before -> {after} after")


if __name__ == "__main__":
    main()
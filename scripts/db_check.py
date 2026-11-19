"""Check that Python can reach PostgreSQL and that pgvector is enabled."""

from urllib.parse import urlparse

import psycopg

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is not set in .env")

    url = settings.database_url.get_secret_value()
    target = urlparse(url)
    print(f"Target: {target.hostname}:{target.port}{target.path}")

    with psycopg.connect(url) as conn:
        version = conn.execute("SELECT version()").fetchone()
        vector = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()

    print(f"Connected: {version[0][:60]}...")
    print(f"pgvector version: {vector[0] if vector else 'NOT ENABLED'}")


if __name__ == "__main__":
    main()
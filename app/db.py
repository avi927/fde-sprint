"""Database connections, with pgvector support registered."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from app.config import get_settings


class DatabaseNotConfiguredError(Exception):
    """Raised when DATABASE_URL is missing from the config."""


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a connection: commit on success, roll back on error, always close."""
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set in .env")

    with psycopg.connect(settings.database_url.get_secret_value()) as conn:
        register_vector(conn)
        yield conn
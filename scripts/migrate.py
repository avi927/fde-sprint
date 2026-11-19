"""Apply SQL migrations from migrations/ in order, each exactly once."""

from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text         PRIMARY KEY,
    applied_at  timestamptz  NOT NULL DEFAULT now()
)
"""


def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is not set in .env")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        raise SystemExit(f"No .sql files found in {MIGRATIONS_DIR}")

    with psycopg.connect(settings.database_url.get_secret_value(), autocommit=True) as conn:
        conn.execute(CREATE_TRACKING_TABLE)
        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

        for path in migration_files:
            if path.name in applied:
                print(f"skip     {path.name}")
                continue

            sql = path.read_text(encoding="utf-8")
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            print(f"applied  {path.name}")

    print("Migrations up to date.")


if __name__ == "__main__":
    main()
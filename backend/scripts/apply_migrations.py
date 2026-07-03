"""Apply the versioned SQL migrations in order, as the database owner.

Run before the integration tests (locally and in CI). The migrations are
idempotent, so re-running against a persistent local database is safe.

    uv run python scripts/apply_migrations.py
"""

import asyncio
import pathlib

import asyncpg

from app.core.settings import get_settings

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[2] / "supabase" / "migrations"


async def main() -> None:
    settings = get_settings()
    connection = await asyncpg.connect(dsn=settings.database_url)
    try:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            await connection.execute(path.read_text(encoding="utf-8"))
            print(f"applied {path.name}")
    finally:
        await connection.close()
    print("migrations complete")


if __name__ == "__main__":
    asyncio.run(main())

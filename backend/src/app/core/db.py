"""The async Postgres connection pool. Created at startup, closed at shutdown."""

import asyncpg

from app.core.settings import Settings

_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 5


async def create_db_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.database_url, min_size=_POOL_MIN_SIZE, max_size=_POOL_MAX_SIZE
    )


async def close_db_pool(pool: asyncpg.Pool) -> None:
    await pool.close()

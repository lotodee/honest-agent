"""The unprivileged asyncpg pool and the single tenant-scoped access path.

The running service connects as app_user (non-owner, non-superuser, no BYPASSRLS)
to the DIRECT database connection (port 5432; 54322 on the local Supabase). The
owner connection that applies migrations is separate and is never held by the app.

Delta 6 (scale note, not today): if this ever runs behind Supavisor transaction
pooling instead of a direct connection, tenant_txn's set_config and its queries
must share one transaction (they do), asyncpg needs statement_cache_size=0, and
LISTEN/NOTIFY does not work. One always-on container on the direct connection
avoids all of that, so it is the chosen profile; SESSION-mode Supavisor is the
fallback if a host cannot reach the direct port (re-check on the Day-9 deploy).
"""

import asyncpg

from app.core.settings import Settings

_POOL_MIN_SIZE = 5
_POOL_MAX_SIZE = 10


async def create_db_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.app_database_url,
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
    )


async def close_db_pool(pool: asyncpg.Pool) -> None:
    await pool.close()

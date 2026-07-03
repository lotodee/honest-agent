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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def tenant_txn(
    pool: asyncpg.Pool, tenant_id: str
) -> AsyncIterator[asyncpg.Connection]:
    """The ONLY path allowed to touch tenant data.

    Sets the RLS tenant for exactly one transaction; set_config(..., true) resets
    at commit or rollback, so a pooled connection can never leak tenant context to
    its next user. The tenant id is a BIND PARAMETER, never interpolated, and an
    unset variable makes every policy evaluate false (fail closed). The ingestion
    worker (Days 3-4) will reuse this same wrapper for its job processing.
    """
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SELECT set_config('app.tenant_id', $1, true)", tenant_id)
        yield conn

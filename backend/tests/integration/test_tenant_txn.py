"""tenant_txn is the single tenant-scoped access path: it sets the GUC, no leak."""

import asyncpg
import pytest

from app.core.db import tenant_txn

pytestmark = pytest.mark.integration

TENANT = "11111111-1111-1111-1111-111111111111"


async def test_tenant_txn_sets_the_tenant_via_bind_param(db_pool: asyncpg.Pool) -> None:
    async with tenant_txn(db_pool, TENANT) as conn:
        value = await conn.fetchval("SELECT current_setting('app.tenant_id', true)")
        assert value == TENANT


async def test_tenant_context_does_not_leak_to_the_next_user(
    db_pool: asyncpg.Pool,
) -> None:
    async with tenant_txn(db_pool, TENANT):
        pass
    # A later borrow of the (possibly same physical) connection sees no tenant:
    # set_config(..., true) is transaction-scoped, so it fails closed.
    async with db_pool.acquire() as conn:
        value = await conn.fetchval("SELECT current_setting('app.tenant_id', true)")
        assert value in (None, "")

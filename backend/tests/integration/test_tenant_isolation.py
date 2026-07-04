"""Day 2, the non-negotiable: tenant A cannot read or write tenant B, in Postgres
AND in Weaviate. The Postgres sweep is dynamic, so a future table that forgets its
wall fails this test by presence rather than by anyone remembering to add a case.
"""

import re
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
import weaviate
from weaviate.exceptions import WeaviateBaseError

from app.core.db import tenant_txn
from app.core.settings import EMBEDDING_DIM, get_settings
from app.retrieval.weaviate import TenantChunks, bootstrap_chunks, connect

pytestmark = pytest.mark.integration

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
UNKNOWN_TENANT = "99999999-9999-9999-9999-999999999999"

# The tenant-scoped tables the cross-tenant test parametrizes over. Kept static so
# nothing connects to the database at collection time; a NEW tenant table that is
# not added here is caught two ways: the dynamic forced-RLS sweep, and the
# discovered-tables-are-all-covered test below (which fails until it is added).
TENANT_TABLES = ("documents", "chunks")

# Public tables that are intentionally NOT tenant-scoped (global public lookups).
_SWEEP_ALLOWLIST = frozenset({"widget_keys"})
_SAFE_IDENTIFIER = re.compile(r"^[a-z_]+$")

_OPEN_TABLES_QUERY = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relforcerowsecurity
"""
_TENANT_TABLES_QUERY = """
SELECT DISTINCT tablename FROM pg_policies
WHERE schemaname = 'public' AND policyname = 'tenant_isolation'
ORDER BY tablename
"""


async def _tenant_tables(pool: asyncpg.Pool) -> list[str]:
    rows = await pool.fetch(_TENANT_TABLES_QUERY)
    return [row["tablename"] for row in rows]


def _vector_literal() -> str:
    # A deterministic placeholder of the correct dimensionality. Real embeddings
    # (Day 5) replace these; Day 2 only needs a well-shaped vector to store.
    dim = EMBEDDING_DIM
    return "[" + ",".join(str((i % 97) / 97.0) for i in range(dim)) + "]"


async def _seed_row(conn: asyncpg.Connection, table: str, tenant_id: str) -> None:
    if table == "documents":
        await conn.execute(
            "INSERT INTO documents (tenant_id, object_key, content_hash) "
            "VALUES ($1, $2, $3)",
            tenant_id,
            f"tenants/{tenant_id}/doc.pdf",
            "placeholder-content-hash",
        )
    elif table == "chunks":
        await conn.execute(
            "INSERT INTO chunks "
            "(tenant_id, document_id, chunk_index, text, content_hash, embedding) "
            "VALUES ($1, $2, $3, $4, $5, $6::vector)",
            tenant_id,
            TENANT_A,
            0,
            "placeholder chunk text",
            "placeholder-content-hash",
            _vector_literal(),
        )
    else:
        pytest.fail(f"no seed defined for discovered tenant table: {table}")


async def _count(conn: asyncpg.Connection, table: str) -> int:
    if not _SAFE_IDENTIFIER.match(table):
        pytest.fail(f"unsafe table name from discovery: {table}")
    value: int = await conn.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
    return value


@pytest_asyncio.fixture
async def _clean_tenant_tables() -> AsyncIterator[None]:
    # Truncate as the owner so each run starts clean and re-runnable. app_user
    # cannot TRUNCATE; only the migration owner can, which is why this uses the
    # owner connection, not the app pool.
    conn = await asyncpg.connect(dsn=get_settings().database_url)
    try:
        await conn.execute("TRUNCATE documents, chunks")
    finally:
        await conn.close()
    yield


# ---- Postgres: the dynamic sweep -------------------------------------------------


async def test_every_app_table_has_forced_rls(db_pool: asyncpg.Pool) -> None:
    rows = await db_pool.fetch(_OPEN_TABLES_QUERY)
    unprotected = [r["relname"] for r in rows if r["relname"] not in _SWEEP_ALLOWLIST]
    assert not unprotected, f"public tables without FORCED RLS: {unprotected}"


async def test_discovered_tenant_tables_are_all_covered(db_pool: asyncpg.Pool) -> None:
    # A new tenant table (one with the tenant_isolation policy) that is not added to
    # TENANT_TABLES fails here, so the cross-tenant proof can never silently skip it.
    discovered = set(await _tenant_tables(db_pool))
    assert discovered == set(TENANT_TABLES), (
        f"discovered {discovered} but the cross-tenant test covers {set(TENANT_TABLES)}"
    )


@pytest.mark.parametrize("table", TENANT_TABLES)
async def test_cross_tenant_read_and_write_blocked(
    db_pool: asyncpg.Pool, _clean_tenant_tables: None, table: str
) -> None:
    async with tenant_txn(db_pool, TENANT_A) as conn:
        await _seed_row(conn, table, TENANT_A)

    async with tenant_txn(db_pool, TENANT_B) as conn:
        assert await _count(conn, table) == 0  # read is sealed
        with pytest.raises(asyncpg.InsufficientPrivilegeError):  # SQLSTATE 42501
            await _seed_row(conn, table, TENANT_A)  # write is sealed by WITH CHECK


# ---- Postgres: metadata and silent-bypass holes ---------------------------------


async def test_app_role_is_non_owner_and_non_bypassrls(db_pool: asyncpg.Pool) -> None:
    row = await db_pool.fetchrow(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    )
    assert row is not None
    assert row["rolsuper"] is False
    assert row["rolbypassrls"] is False


async def test_each_tenant_table_forces_row_security(db_pool: asyncpg.Pool) -> None:
    tables = await _tenant_tables(db_pool)
    assert tables, "no tenant tables discovered; the sweep would be vacuous"
    for table in tables:
        forced = await db_pool.fetchval(
            "SELECT relforcerowsecurity FROM pg_class WHERE relname = $1", table
        )
        assert forced is True, f"{table} does not FORCE row security"


async def test_no_security_definer_functions_in_app_schema(
    db_pool: asyncpg.Pool,
) -> None:
    rows = await db_pool.fetch(
        "SELECT p.proname FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.prosecdef"
    )
    assert not [r["proname"] for r in rows], "SECURITY DEFINER functions can bypass RLS"


async def test_all_app_views_are_security_invoker(db_pool: asyncpg.Pool) -> None:
    rows = await db_pool.fetch(
        "SELECT c.relname, c.reloptions FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'v'"
    )
    offenders = [
        r["relname"]
        for r in rows
        if "security_invoker=true" not in (r["reloptions"] or [])
        and "security_invoker=on" not in (r["reloptions"] or [])
    ]
    assert not offenders, f"views not declared security_invoker: {offenders}"


# ---- Weaviate: separate-shard isolation -----------------------------------------
# Native multi-tenancy isolates by separate shards, so the proof is "objects
# written under A are never visible or reachable through B's handle." There is no
# role-based write-block here the way Postgres RLS provides one.


@pytest_asyncio.fixture
async def weaviate_client() -> AsyncIterator[weaviate.WeaviateAsyncClient]:
    client = await connect(get_settings())
    try:
        await bootstrap_chunks(client, [TENANT_A, TENANT_B])
        yield client
    finally:
        await client.close()


async def test_weaviate_cross_tenant_read_blocked(
    weaviate_client: weaviate.WeaviateAsyncClient,
) -> None:
    tenant_a = TenantChunks(weaviate_client, TENANT_A)
    tenant_b = TenantChunks(weaviate_client, TENANT_B)
    await tenant_a.insert(
        document_id="doc-a",
        chunk_index=0,
        text="visible only to tenant A",
        vector=[0.1] * EMBEDDING_DIM,
    )
    assert await tenant_a.count() >= 1  # A sees its own object
    assert await tenant_b.count() == 0  # B never sees A's object through its handle


async def test_weaviate_unknown_tenant_hard_fails(
    weaviate_client: weaviate.WeaviateAsyncClient,
) -> None:
    # auto_tenant_creation is OFF, so a wrong tenant errors instead of silently
    # creating a fresh shard.
    with pytest.raises(WeaviateBaseError):
        await TenantChunks(weaviate_client, UNKNOWN_TENANT).count()

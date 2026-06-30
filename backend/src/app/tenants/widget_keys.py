"""The widget-key store. Keys are PUBLIC identifiers, stored unhashed in Postgres.

Their safety comes from Origin binding + rate limit + narrow scope, not secrecy,
so they are looked up by exact value. Each row maps a key to its tenant and the
exact hosts allowed to use it.
"""

from dataclasses import dataclass
from typing import Protocol

import asyncpg


@dataclass(frozen=True, slots=True)
class WidgetKeyRecord:
    tenant_id: str
    allowed_hosts: frozenset[str]


class WidgetKeyStore(Protocol):
    async def lookup(self, widget_key: str) -> WidgetKeyRecord | None: ...


class InMemoryWidgetKeyStore:
    """Used by unit tests so the gate is provable without a live database."""

    def __init__(self, records: dict[str, WidgetKeyRecord]) -> None:
        self._records = records

    async def lookup(self, widget_key: str) -> WidgetKeyRecord | None:
        return self._records.get(widget_key)


class PostgresWidgetKeyStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, widget_key: str) -> WidgetKeyRecord | None:
        # Parameterized query: the key is bound, never string-built, so a crafted
        # key cannot inject SQL.
        row = await self._pool.fetchrow(
            "SELECT tenant_id, allowed_hosts FROM widget_keys WHERE key = $1",
            widget_key,
        )
        if row is None:
            return None
        return WidgetKeyRecord(
            tenant_id=row["tenant_id"],
            allowed_hosts=frozenset(host.lower() for host in row["allowed_hosts"]),
        )

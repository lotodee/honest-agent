"""Weaviate tenancy: the Chunk collection, two explicit tenants, tenant-bound access.

Native multi-tenancy (one shard per tenant) makes an unscoped query structurally
impossible, and auto_tenant_creation is OFF so a mistyped tenant hard-fails instead
of silently creating a shard (Delta 7). Weaviate is only a rebuildable derived
index; Postgres is the source of truth (locked decision 3), so hybrid search over
these chunks is wired on Day 5, not here.
"""

from typing import Any
from urllib.parse import urlsplit

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.tenants import Tenant

from app.core.settings import Settings

CHUNK_COLLECTION = "Chunk"
_DEFAULT_GRPC_PORT = 50051


def tenant_name(tenant_id: str) -> str:
    """A Weaviate-safe shard name derived from the tenant id (hyphens are invalid)."""
    return "tenant_" + tenant_id.replace("-", "_")


async def connect(settings: Settings) -> weaviate.WeaviateAsyncClient:
    parts = urlsplit(settings.weaviate_url)
    client = weaviate.use_async_with_local(
        host=parts.hostname or "localhost",
        port=parts.port or 8080,
        grpc_port=_DEFAULT_GRPC_PORT,
    )
    await client.connect()
    return client


async def bootstrap_chunks(
    client: weaviate.WeaviateAsyncClient, tenant_ids: list[str]
) -> None:
    """Create the Chunk collection (MT on, self-provided vectors) and the given
    tenants EXPLICITLY. Idempotent: existing collection and tenants are left alone.
    """
    if not await client.collections.exists(CHUNK_COLLECTION):
        await client.collections.create(
            name=CHUNK_COLLECTION,
            multi_tenancy_config=Configure.multi_tenancy(
                enabled=True, auto_tenant_creation=False
            ),
            vector_config=Configure.Vectors.self_provided(),
            properties=[
                Property(name="document_id", data_type=DataType.TEXT),
                Property(name="chunk_index", data_type=DataType.INT),
                Property(name="text", data_type=DataType.TEXT),
            ],
        )
    collection = client.collections.use(CHUNK_COLLECTION)
    existing = await collection.tenants.get()
    missing = [
        Tenant(name=name)
        for name in (tenant_name(t) for t in tenant_ids)
        if name not in existing
    ]
    if missing:
        await collection.tenants.create(missing)


class TenantChunks:
    """A tenant-bound handle. Every operation is scoped to one tenant's shard, so
    reaching a chunk without a tenant is structurally impossible, not just avoided.
    """

    def __init__(self, client: weaviate.WeaviateAsyncClient, tenant_id: str) -> None:
        self._collection = client.collections.use(CHUNK_COLLECTION).with_tenant(
            tenant_name(tenant_id)
        )

    async def insert(
        self,
        *,
        document_id: str,
        chunk_index: int,
        text: str,
        vector: list[float],
    ) -> None:
        properties: dict[str, Any] = {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": text,
        }
        await self._collection.data.insert(properties=properties, vector=vector)

    async def count(self) -> int:
        result = await self._collection.query.fetch_objects(limit=1000)
        return len(result.objects)

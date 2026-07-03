"""The retrieve capability. Day-1 stub; real tenant-scoped hybrid search is Day 5."""

from app.agent.schemas import Source


async def retrieve(tenant_id: str, query: str) -> list[Source]:
    # Day-1 stub: returns a single typed placeholder so the shape is exercised.
    # Real tenant-scoped hybrid search over the tenant's Weaviate shard is Day 5;
    # tenant_id is already the scope boundary that work will enforce.
    return [Source(document_id="stub-document", chunk_id="stub-chunk", score=1.0)]

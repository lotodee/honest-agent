"""Integration layer smoke test: the app answers over ASGI, no external services."""

import pytest
from httpx import AsyncClient

from app.core.db import DatabaseSessions
from app.core.deps import Tenant

pytestmark = pytest.mark.integration


async def test_openapi_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Honest Agent"


def test_two_tenant_seed_is_distinct(
    seeded_tenants: tuple[Tenant, Tenant], db_session: DatabaseSessions
) -> None:
    tenant_a, tenant_b = seeded_tenants
    assert tenant_a.tenant_id != tenant_b.tenant_id
    assert db_session.database_url

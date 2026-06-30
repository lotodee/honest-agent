"""No token, widget key, or Authorization value is ever recorded in structlog.

The auth paths deliberately emit no log lines carrying a credential. These tests
capture the structlog event stream across credential-bearing requests and assert
the credential is absent, so a future log call that leaked one would fail here.
"""

import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from app.tenants.rate_limit import AllowAllRateLimiter
from app.tenants.widget_keys import InMemoryWidgetKeyStore, WidgetKeyRecord

pytestmark = pytest.mark.integration

WIDGET_KEY = "wk_secret_looking_value_should_never_be_logged"
BEARER = "owner.jwt.secret-bearer-value-should-never-be-logged"


@pytest_asyncio.fixture
async def wired_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    app.state.widget_key_store = InMemoryWidgetKeyStore(
        {WIDGET_KEY: WidgetKeyRecord("tenant-a", frozenset({"tenant-a.example.com"}))}
    )
    app.state.rate_limiter = AllowAllRateLimiter()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_widget_key_never_appears_in_structlog(wired_client: AsyncClient) -> None:
    with capture_logs() as logs:
        await wired_client.post(
            "/v1/widget/answer",
            headers={
                "X-Widget-Key": WIDGET_KEY,
                "Origin": "https://tenant-a.example.com",
            },
            json={"query": "hello"},
        )
    assert WIDGET_KEY not in json.dumps(logs)


async def test_authorization_value_never_appears_in_structlog(
    wired_client: AsyncClient,
) -> None:
    with capture_logs() as logs:
        await wired_client.get(
            "/v1/tenants/me", headers={"Authorization": f"Bearer {BEARER}"}
        )
    assert BEARER not in json.dumps(logs)

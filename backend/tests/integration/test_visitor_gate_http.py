"""The visitor door over real HTTP: the middleware, the route, and the error shapes."""

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.tenants.rate_limit import AllowAllRateLimiter
from app.tenants.widget_keys import InMemoryWidgetKeyStore, WidgetKeyRecord

pytestmark = pytest.mark.integration

KEY_A = "wk_tenant_a_public"
ALLOWED_ORIGIN = "https://tenant-a.example.com"


@pytest_asyncio.fixture
async def widget_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # The widget-key store and limiter are normally wired in the lifespan; inject
    # an in-memory store so the full middleware path runs without a database.
    app.state.widget_key_store = InMemoryWidgetKeyStore(
        {KEY_A: WidgetKeyRecord("tenant-a", frozenset({"tenant-a.example.com"}))}
    )
    app.state.rate_limiter = AllowAllRateLimiter()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_allowed_request_reaches_the_stub_core(
    widget_client: AsyncClient,
) -> None:
    response = await widget_client.post(
        "/v1/widget/answer",
        headers={"X-Widget-Key": KEY_A, "Origin": ALLOWED_ORIGIN},
        json={"query": "how do I rotate a key?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["kind"] == "grounded"
    assert body["answer"]


async def test_disallowed_origin_is_403(widget_client: AsyncClient) -> None:
    response = await widget_client.post(
        "/v1/widget/answer",
        headers={"X-Widget-Key": KEY_A, "Origin": "https://evil.com"},
        json={"query": "hi"},
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_unknown_key_is_401(widget_client: AsyncClient) -> None:
    response = await widget_client.post(
        "/v1/widget/answer",
        headers={"X-Widget-Key": "wk_unknown", "Origin": ALLOWED_ORIGIN},
        json={"query": "hi"},
    )
    assert response.status_code == 401


async def test_oversized_body_is_413(widget_client: AsyncClient) -> None:
    response = await widget_client.post(
        "/v1/widget/answer",
        headers={"X-Widget-Key": KEY_A, "Origin": ALLOWED_ORIGIN},
        json={"query": "x" * 200_000},
    )
    assert response.status_code == 413


async def test_no_secret_leaks_in_a_rejection(
    widget_client: AsyncClient, assert_no_secret_leak: Callable[[str], None]
) -> None:
    response = await widget_client.post(
        "/v1/widget/answer",
        headers={"X-Widget-Key": "wk_unknown", "Origin": ALLOWED_ORIGIN},
        json={"query": "hi"},
    )
    assert_no_secret_leak(response.text)

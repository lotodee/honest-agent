"""The owner body-cap must guard the REAL tenants route surface built by create_app().

The unit test in test_owner_body_cap.py proves the middleware logic on a hand-built app.
This proves the WIRING: it drives an oversized body through the real create_app() at the
tenants router's own mounted path (derived from the router, the single source of truth),
so if the cap's prefix ever diverges from where the router is actually mounted, the body
is not rejected and this test fails loudly instead of the control silently evaporating.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.settings import get_settings
from app.tenants.router import router as tenants_router

pytestmark = pytest.mark.integration


async def test_owner_cap_guards_the_real_tenants_route_path(app: FastAPI) -> None:
    over_cap = get_settings().visitor_max_body_bytes + 1
    # POST (not GET /me) so the body-cap middleware, which runs before routing, is what
    # rejects it — no owner route needs to accept a body for this to hold.
    target = f"/v1{tenants_router.prefix}/me"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(target, content=b"x" * over_cap)
    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/problem+json")

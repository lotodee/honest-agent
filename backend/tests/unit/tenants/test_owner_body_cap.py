"""The owner-door body cap: reject an over-large body on owner routes, and prove the
scope so the future /v1/ingestion upload path is not accidentally throttled."""

import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from app.tenants.owner_gate import install_owner_body_cap

_CAP = 100


def _app() -> FastAPI:
    app = FastAPI()
    install_owner_body_cap(app, "/v1/tenants", max_body_bytes=_CAP)

    @app.post("/v1/tenants/echo")
    async def tenants_echo() -> dict[str, str]:
        return {"door": "owner"}

    @app.post("/v1/ingestion/echo")
    async def ingestion_echo() -> dict[str, str]:
        return {"door": "ingestion"}

    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_oversized_owner_body_is_rejected_before_the_route() -> None:
    async with await _client(_app()) as client:
        response = await client.post("/v1/tenants/echo", content=b"x" * (_CAP + 1))
    assert response.status_code == 413


async def test_small_owner_body_passes() -> None:
    async with await _client(_app()) as client:
        response = await client.post("/v1/tenants/echo", content=b"x" * 10)
    assert response.status_code == 200
    assert response.json() == {"door": "owner"}


async def test_ingestion_path_is_not_capped() -> None:
    # The cap is scoped to /v1/tenants; the upload path must be free to carry a body
    # larger than the owner cap.
    async with await _client(_app()) as client:
        response = await client.post("/v1/ingestion/echo", content=b"x" * (_CAP + 500))
    assert response.status_code == 200
    assert response.json() == {"door": "ingestion"}


async def test_overlong_content_length_is_clean_400_not_500() -> None:
    # A crafted all-digit Content-Length past CPython's 4300-digit int() limit passes
    # str.isdigit() but would make int() raise. That must surface as a clean RFC 9457
    # 400, never fall through to an unauthenticated generic 500.
    async with await _client(_app()) as client:
        response = await client.post(
            "/v1/tenants/echo", headers={"content-length": "1" * 4301}, content=b""
        )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 400

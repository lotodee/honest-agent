"""Shared fixtures for all three test layers. Stubs that import and collect cleanly."""

import os
from collections.abc import AsyncIterator, Callable

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.db import close_db_pool, create_db_pool
from app.core.deps import Tenant
from app.core.settings import Settings, get_settings, secret_values
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _local_settings_env() -> None:
    # The app fails loudly without its required settings, so tests supply local
    # dummies before the first construction. Real values come from env or .env.
    # The two secret values are set so the secret-leak guards have something real
    # to look for.
    # DB defaults point at the real local stack so integration tests connect; CI
    # overrides them with its own service env. Unit tests never open a connection.
    defaults = {
        "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        "APP_DATABASE_URL": "postgresql://app_user:app_user_local_pw@127.0.0.1:54322/postgres",
        "WEAVIATE_URL": "http://localhost:8080",
        "SUPABASE_JWT_ISSUER": "http://127.0.0.1:54321/auth/v1",
        "SUPABASE_JWKS_URL": "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-secret-must-never-leak",
        "MCP_SIGNING_SECRET": "test-mcp-signing-secret-0123456789abcdef",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # In-process ASGI transport: no socket, full async lifecycle. The Bearer auth
    # header attaches here once Supabase auth lands; today the seam is open.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
def seeded_tenants() -> tuple[Tenant, Tenant]:
    # The two tenants the Day-2 isolation test proves cannot read or write each other.
    return Tenant("tenant-a"), Tenant("tenant-b")


@pytest_asyncio.fixture
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    # The unprivileged app_user pool against the real database. Integration only;
    # migrations must have been applied first (scripts/apply_migrations.py).
    pool = await create_db_pool(get_settings())
    try:
        yield pool
    finally:
        await close_db_pool(pool)


@pytest.fixture
def assert_no_secret_leak(settings: Settings) -> Callable[[str], None]:
    # Reusable across the doors: assert no configured secret value appears in a
    # response body or a captured log line.
    secrets = secret_values(settings)

    def _check(text: str) -> None:
        for secret in secrets:
            assert secret not in text, "a server secret leaked into client-facing text"

    return _check

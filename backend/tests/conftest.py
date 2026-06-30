"""Shared fixtures for all three test layers. Stubs that import and collect cleanly."""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.db import DatabaseSessions, build_db_sessions
from app.core.deps import Tenant
from app.core.settings import Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _local_settings_env() -> None:
    # The app fails loudly without its required settings, so tests supply local
    # dummies before the first construction. Real values come from env or .env.
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://localhost:5432/honest_agent_test"
    )
    os.environ.setdefault("WEAVIATE_URL", "http://localhost:8080")
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
def db_session(settings: Settings) -> DatabaseSessions:
    # Stands in for the transactional, per-test session that rolls back once the
    # async engine is wired; for now it is the typed seam carrying the URL.
    return build_db_sessions(settings)


@pytest.fixture
def seeded_tenants() -> tuple[Tenant, Tenant]:
    # The two tenants the Day-2 isolation test proves cannot read or write each other.
    return Tenant("tenant-a"), Tenant("tenant-b")

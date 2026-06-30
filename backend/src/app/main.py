"""The app factory. Builds settings, wires observability, errors, the gate, routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.agent.router import router as agent_router
from app.core.db import close_db_pool, create_db_pool
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.observability import configure_observability
from app.core.settings import Settings, get_settings
from app.eval.router import router as eval_router
from app.guardrails.router import router as guardrails_router
from app.ingestion.router import router as ingestion_router
from app.mcp.router import router as mcp_router
from app.retrieval.router import router as retrieval_router
from app.tenants.gate import VisitorGate, install_visitor_gate
from app.tenants.rate_limit import AllowAllRateLimiter
from app.tenants.router import router as tenants_router
from app.tenants.widget_keys import PostgresWidgetKeyStore
from app.tenants.widget_router import router as widget_router

_DOMAIN_ROUTERS: tuple[APIRouter, ...] = (
    tenants_router,
    ingestion_router,
    agent_router,
    retrieval_router,
    guardrails_router,
    eval_router,
    mcp_router,
    widget_router,
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_db_pool(settings)
    app.state.db_pool = pool
    app.state.widget_key_store = PostgresWidgetKeyStore(pool)
    app.state.rate_limiter = AllowAllRateLimiter()
    try:
        yield
    finally:
        await close_db_pool(pool)


def _visitor_gate(app: FastAPI, settings: Settings) -> VisitorGate:
    return VisitorGate(
        store=app.state.widget_key_store,
        rate_limiter=app.state.rate_limiter,
        max_body_bytes=settings.visitor_max_body_bytes,
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Honest Agent", version="0.1.0", lifespan=_lifespan)
    configure_observability(app, settings)
    register_error_handlers(app)
    install_visitor_gate(app, lambda: _visitor_gate(app, settings))
    for router in _DOMAIN_ROUTERS:
        app.include_router(router, prefix="/v1")
    return app

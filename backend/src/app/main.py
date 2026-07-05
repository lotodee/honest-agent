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
from app.mcp.server import (
    McpSecurityMiddleware,
    build_mcp_server,
    build_mcp_verifier,
    mcp_allowed_origin_hosts,
    mcp_request_hosts,
)
from app.retrieval.router import router as retrieval_router
from app.tenants.gate import VisitorGate, install_visitor_gate
from app.tenants.owner_gate import install_owner_body_cap
from app.tenants.rate_limit import AllowAllRateLimiter
from app.tenants.router import router as tenants_router
from app.tenants.widget_keys import PostgresWidgetKeyStore
from app.tenants.widget_router import router as widget_router

# The MCP server and its ASGI app are built once; the session manager is started
# in the lifespan and the app is mounted (secured) under /mcp in create_app.
_mcp_server = build_mcp_server()
_mcp_app = _mcp_server.streamable_http_app()

_DOMAIN_ROUTERS: tuple[APIRouter, ...] = (
    tenants_router,
    ingestion_router,
    agent_router,
    retrieval_router,
    guardrails_router,
    eval_router,
    widget_router,
)

# The single API version prefix. Used both to mount the routers and to derive the owner
# body-cap's guarded prefix, so the two cannot drift.
_API_PREFIX = "/v1"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_db_pool(settings)
    app.state.db_pool = pool
    app.state.widget_key_store = PostgresWidgetKeyStore(pool)
    app.state.rate_limiter = AllowAllRateLimiter()
    async with _mcp_server.session_manager.run():
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
    # Owner routes share the visitor door's body-size cap (defense-in-depth). Derive the
    # guarded prefix from the tenants router's real mounted path so a prefix rename
    # cannot silently unguard it.
    install_owner_body_cap(
        app, f"{_API_PREFIX}{tenants_router.prefix}", settings.visitor_max_body_bytes
    )
    for router in _DOMAIN_ROUTERS:
        app.include_router(router, prefix=_API_PREFIX)
    app.mount(
        "/mcp",
        McpSecurityMiddleware(
            _mcp_app,
            verifier=build_mcp_verifier(settings),
            allowed_origin_hosts=mcp_allowed_origin_hosts(settings),
            allowed_request_hosts=mcp_request_hosts(settings),
        ),
    )
    return app

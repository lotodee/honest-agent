"""The app factory. Builds settings, wires observability and errors, mounts routers."""

from fastapi import APIRouter, FastAPI

from app.agent.router import router as agent_router
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.observability import configure_observability
from app.core.settings import get_settings
from app.eval.router import router as eval_router
from app.guardrails.router import router as guardrails_router
from app.ingestion.router import router as ingestion_router
from app.mcp.router import router as mcp_router
from app.retrieval.router import router as retrieval_router
from app.tenants.router import router as tenants_router

_DOMAIN_ROUTERS: tuple[APIRouter, ...] = (
    tenants_router,
    ingestion_router,
    agent_router,
    retrieval_router,
    guardrails_router,
    eval_router,
    mcp_router,
)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Honest Agent", version="0.1.0")
    configure_observability(app, settings)
    register_error_handlers(app)
    for router in _DOMAIN_ROUTERS:
        app.include_router(router, prefix="/v1")
    return app

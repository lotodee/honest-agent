"""structlog configured to render JSON, bound to tenant/request/trace id."""

import logging

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.typing import Processor


def configure_logging(*, json_logs: bool = True) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_request_context(*, tenant_id: str, request_id: str, trace_id: str) -> None:
    clear_contextvars()
    bind_contextvars(tenant_id=tenant_id, request_id=request_id, trace_id=trace_id)

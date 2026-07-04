"""The visitor widget-key gate: in-app FastAPI middleware on the widget path.

In order: body-size cap (before parsing), key-exists, Origin/Referer allowlist
(exact host), rate limit (stubbed seam), then sanitize to just the query. The
resolved tenant comes ONLY from the key row; no request input can set or change it.
The gate calls the core in-process via the thin adapter, never through the MCP.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.core.content_length import parse_content_length
from app.core.errors import (
    AppError,
    AuthenticationError,
    BadRequestError,
    PayloadTooLargeError,
    RateLimitedError,
    TenantAccessError,
    app_error_response,
)
from app.core.origins import host_allowed
from app.tenants.contexts import VisitorRequestContext
from app.tenants.rate_limit import RateLimiter
from app.tenants.widget_keys import WidgetKeyStore

WIDGET_PATH_PREFIX = "/v1/widget"
WIDGET_KEY_HEADER = "x-widget-key"


@dataclass(frozen=True, slots=True)
class VisitorGate:
    store: WidgetKeyStore
    rate_limiter: RateLimiter
    max_body_bytes: int

    async def authorize(
        self,
        *,
        widget_key: str | None,
        origin: str | None,
        referer: str | None,
        client_ip: str | None,
        body: bytes,
    ) -> VisitorRequestContext:
        if len(body) > self.max_body_bytes:
            raise PayloadTooLargeError("request body exceeds the visitor limit")
        if not widget_key:
            raise AuthenticationError("missing widget key")
        record = await self.store.lookup(widget_key)
        if record is None:
            raise AuthenticationError("unknown widget key")
        self._check_origin(origin, referer, record.allowed_hosts)
        allowed = await self.rate_limiter.check(
            widget_key=widget_key, client_ip=client_ip
        )
        if not allowed:
            raise RateLimitedError("rate limit exceeded")
        return VisitorRequestContext(
            tenant_id=record.tenant_id, query=self._sanitize_query(body)
        )

    def _check_origin(
        self, origin: str | None, referer: str | None, allowed_hosts: frozenset[str]
    ) -> None:
        # A present Origin is authoritative; never fall back to a forgeable Referer
        # when the browser sent one, and never treat empty or `null` as allowed.
        if origin is not None:
            if not host_allowed(origin, allowed_hosts):
                raise TenantAccessError("origin not allowed")
            return
        if referer is not None:
            if not host_allowed(referer, allowed_hosts):
                raise TenantAccessError("origin not allowed")
            return
        raise TenantAccessError("request carries no origin or referer")

    def _sanitize_query(self, body: bytes) -> str:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise BadRequestError("request body is not valid json") from exc
        if not isinstance(payload, dict):
            raise BadRequestError("request body must be a json object")
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise BadRequestError("request must carry a non-empty query")
        # Only the query survives. Any smuggled tenant/role/origin_override field is
        # dropped here: the tenant comes solely from the verified key row.
        return query


def install_visitor_gate(app: FastAPI, provide_gate: Callable[[], VisitorGate]) -> None:
    @app.middleware("http")
    async def visitor_gate_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith(WIDGET_PATH_PREFIX):
            return await call_next(request)
        gate = provide_gate()
        instance = request.url.path
        try:
            declared = parse_content_length(request.headers.get("content-length"))
        except AppError as exc:
            # Malformed length (non-digit, or so long int() would raise): a bad request,
            # not a 500. This is the zero-auth door, so surface it cleanly via RFC 9457.
            return app_error_response(exc, instance=instance)
        if declared is not None and declared > gate.max_body_bytes:
            return app_error_response(
                PayloadTooLargeError("declared body exceeds the visitor limit"),
                instance=instance,
            )
        body = await request.body()
        try:
            context = await gate.authorize(
                widget_key=request.headers.get(WIDGET_KEY_HEADER),
                origin=request.headers.get("origin"),
                referer=request.headers.get("referer"),
                client_ip=request.client.host if request.client else None,
                body=body,
            )
        except AppError as exc:
            return app_error_response(exc, instance=instance)
        request.state.visitor_context = context
        return await call_next(request)

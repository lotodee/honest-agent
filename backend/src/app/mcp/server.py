"""The secured Streamable-HTTP MCP server: one tool, Origin- and token-checked.

The OAuth 2.1 Resource Server discipline here is the validation, not a full OAuth
stack: check the token's signature, issuer, audience (this server), and expiry,
reject anything not minted for this server, validate the Origin header, and never
forward the inbound token upstream. The fuller machinery (Protected Resource
Metadata per RFC 9728, dynamic client registration, PKCE) is the Day-12 write-up.
"""

import contextvars

from mcp.server.fastmcp import FastMCP
from starlette.types import ASGIApp, Receive, Scope, Send

from app.agent.adapters import answer_for_external_caller
from app.core.bearer import parse_bearer
from app.core.errors import (
    AppError,
    AuthenticationError,
    TenantAccessError,
    app_error_response,
)
from app.core.origins import host_allowed, origin_host
from app.core.settings import Settings
from app.mcp.tokens import McpTokenVerifier
from app.tenants.contexts import ExternalCallerContext

_external_caller: contextvars.ContextVar[ExternalCallerContext | None] = (
    contextvars.ContextVar("mcp_external_caller", default=None)
)

_TOOL_DESCRIPTION = (
    "Answer a question for the caller's tenant, fused with an honesty verdict."
)


def build_mcp_server() -> FastMCP:
    server = FastMCP("honest-agent", stateless_http=True, streamable_http_path="/")

    @server.tool(description=_TOOL_DESCRIPTION)
    async def answer(query: str) -> dict[str, object]:
        context = _external_caller.get()
        if context is None:
            # The security middleware sets this on every verified request, so its
            # absence means the tool was reached without verification.
            raise AuthenticationError("mcp caller was not verified")
        result = await answer_for_external_caller(context, query)
        return result.model_dump()

    return server


def mcp_allowed_hosts(settings: Settings) -> frozenset[str]:
    hosts = {origin_host(origin) for origin in settings.mcp_allowed_origins}
    return frozenset(host for host in hosts if host is not None)


def build_mcp_verifier(settings: Settings) -> McpTokenVerifier:
    return McpTokenVerifier(
        secret=settings.mcp_signing_secret,
        issuer=settings.mcp_token_issuer,
        audience=settings.mcp_token_audience,
    )


class McpSecurityMiddleware:
    """Origin check (DNS-rebinding defense) then external-caller token verification.

    On success the verified tenant is placed in a contextvar the tool reads. The
    inbound token is never written to the scope or forwarded anywhere downstream.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        verifier: McpTokenVerifier,
        allowed_hosts: frozenset[str],
    ) -> None:
        self._app = app
        self._verifier = verifier
        self._allowed_hosts = allowed_hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = {
            key.decode().lower(): value.decode() for key, value in scope["headers"]
        }
        instance = str(scope.get("path", "/mcp"))
        try:
            self._check_origin(headers.get("origin"))
            context = self._verifier.verify(parse_bearer(headers.get("authorization")))
        except AppError as exc:
            await app_error_response(exc, instance=instance)(scope, receive, send)
            return
        reset_token = _external_caller.set(context)
        try:
            await self._app(scope, receive, send)
        finally:
            _external_caller.reset(reset_token)

    def _check_origin(self, origin: str | None) -> None:
        if origin is not None and not host_allowed(origin, self._allowed_hosts):
            raise TenantAccessError("origin not allowed")

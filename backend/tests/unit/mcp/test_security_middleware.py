"""The MCP security middleware: Origin 403, token reject, and no token passthrough."""

from typing import Any

from app.mcp.server import McpSecurityMiddleware, _external_caller
from app.mcp.tokens import McpTokenVerifier, mint_mcp_token

SECRET = "mcp-signing-secret-under-test-0123456789"  # noqa: S105
ISSUER = "honest-agent"
AUDIENCE = "honest-agent-mcp"
ALLOWED_ORIGINS = frozenset({"claude.ai"})
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})


class _InnerApp:
    """Records whether it ran and what it could see, standing in for the MCP app."""

    def __init__(self) -> None:
        self.ran = False
        self.seen_tenant: str | None = None
        self.seen_headers: dict[str, str] = {}

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.ran = True
        caller = _external_caller.get()
        self.seen_tenant = caller.tenant_id if caller is not None else None
        self.seen_headers = {
            k.decode().lower(): v.decode() for k, v in scope["headers"]
        }


def _scope(headers: dict[str, str]) -> dict[str, Any]:
    # Default to a legitimate Host so origin/token tests are not tripped by the
    # Host check; tests that probe rebinding override "host" explicitly.
    merged = {"host": "127.0.0.1", **headers}
    raw = [(k.lower().encode(), v.encode()) for k, v in merged.items()]
    return {"type": "http", "path": "/mcp", "headers": raw}


async def _capture_send() -> tuple[list[dict[str, Any]], Any]:
    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    return messages, send


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _middleware(inner: _InnerApp) -> McpSecurityMiddleware:
    return McpSecurityMiddleware(
        inner,
        verifier=McpTokenVerifier(secret=SECRET, issuer=ISSUER, audience=AUDIENCE),
        allowed_origin_hosts=ALLOWED_ORIGINS,
        allowed_request_hosts=ALLOWED_HOSTS,
    )


def _valid_token() -> str:
    return mint_mcp_token(
        secret=SECRET, issuer=ISSUER, audience=AUDIENCE, tenant_id="tenant-a"
    )


async def test_valid_token_and_origin_runs_inner_with_tenant() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope(
            {"authorization": f"Bearer {_valid_token()}", "origin": "https://claude.ai"}
        ),
        _noop_receive,
        send,
    )
    assert inner.ran
    assert inner.seen_tenant == "tenant-a"


async def test_disallowed_origin_is_403_and_inner_never_runs() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope(
            {"authorization": f"Bearer {_valid_token()}", "origin": "https://evil.com"}
        ),
        _noop_receive,
        send,
    )
    assert not inner.ran
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 403


async def test_forged_host_is_403_and_inner_never_runs() -> None:
    # DNS-rebinding: a rebound Host the server does not serve under is rejected,
    # even with a valid token and an allowed Origin.
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope(
            {
                "host": "attacker.com",
                "authorization": f"Bearer {_valid_token()}",
                "origin": "https://claude.ai",
            }
        ),
        _noop_receive,
        send,
    )
    assert not inner.ran
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 403


async def test_missing_host_is_rejected() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    scope = _scope(
        {"authorization": f"Bearer {_valid_token()}", "origin": "https://claude.ai"}
    )
    scope["headers"] = [h for h in scope["headers"] if h[0] != b"host"]
    await _middleware(inner)(scope, _noop_receive, send)
    assert not inner.ran
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 403


async def test_bad_token_is_rejected_and_inner_never_runs() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope(
            {"authorization": "Bearer not-a-real-token", "origin": "https://claude.ai"}
        ),
        _noop_receive,
        send,
    )
    assert not inner.ran
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 401


async def test_missing_token_is_rejected() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope({"origin": "https://claude.ai"}), _noop_receive, send
    )
    assert not inner.ran
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 401


async def test_context_is_reset_after_the_request() -> None:
    inner = _InnerApp()
    messages, send = await _capture_send()
    await _middleware(inner)(
        _scope(
            {"authorization": f"Bearer {_valid_token()}", "origin": "https://claude.ai"}
        ),
        _noop_receive,
        send,
    )
    # No request in flight, so the verified caller must not linger in the contextvar.
    assert _external_caller.get() is None

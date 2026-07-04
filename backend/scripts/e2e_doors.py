"""End-to-end proof of the three doors over real HTTP. Re-runnable.

Assumes the app is running (default http://127.0.0.1:8000) and the local stack is
seeded (scripts/seed_local.py). Exercises the owner, visitor, and MCP doors with
both accept and reject cases, prints a PASS/FAIL line each, and exits non-zero if
any case fails.

    uv run python scripts/seed_local.py
    uv run uvicorn app.main:create_app --factory --port 8000   # in another shell
    uv run python scripts/e2e_doors.py
"""

import asyncio
import os
import sys
from typing import NamedTuple

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from scripts.seed_local import OWNER_PASSWORD

from app.core.settings import get_settings
from app.mcp.tokens import mint_mcp_token

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
_results: list[tuple[bool, str]] = []


def _check(passed: bool, label: str) -> None:
    _results.append((passed, label))
    print(f"{'PASS' if passed else 'FAIL'}  {label}")


async def _supabase_owner_token(email: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": settings.supabase_anon_key or ""},
            json={"email": email, "password": OWNER_PASSWORD},
        )
        response.raise_for_status()
        token: str = response.json()["access_token"]
        return token


async def _owner_door() -> None:
    print("\n== OWNER DOOR ==")
    token = await _supabase_owner_token("owner-a@example.com")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        ok = await client.get(
            "/v1/tenants/me", headers={"Authorization": f"Bearer {token}"}
        )
        _check(
            ok.status_code == 200 and ok.json().get("tenant_id") == "tenant-a",
            f"valid Supabase token accepted, tenant resolved ({ok.status_code})",
        )
        none = await client.get("/v1/tenants/me")
        _check(none.status_code == 401, f"no token rejected ({none.status_code})")
        junk = await client.get(
            "/v1/tenants/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        _check(junk.status_code == 401, f"garbage token rejected ({junk.status_code})")


async def _visitor_door() -> None:
    print("\n== VISITOR DOOR ==")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        good = await client.post(
            "/v1/widget/answer",
            headers={
                "X-Widget-Key": "wk_tenant_a_public",
                "Origin": "https://tenant-a.example.com",
            },
            json={"query": "how do I rotate a key?"},
        )
        body = good.json() if good.status_code == 200 else {}
        _check(
            good.status_code == 200
            and body.get("verdict", {}).get("kind") == "grounded",
            f"allowed key + origin reaches core, verdict fused ({good.status_code})",
        )
        bad_origin = await client.post(
            "/v1/widget/answer",
            headers={
                "X-Widget-Key": "wk_tenant_a_public",
                "Origin": "https://evil.com",
            },
            json={"query": "hi"},
        )
        _check(
            bad_origin.status_code == 403,
            f"disallowed origin 403 ({bad_origin.status_code})",
        )
        unknown = await client.post(
            "/v1/widget/answer",
            headers={
                "X-Widget-Key": "wk_unknown",
                "Origin": "https://tenant-a.example.com",
            },
            json={"query": "hi"},
        )
        _check(
            unknown.status_code == 401, f"unknown key rejected ({unknown.status_code})"
        )


class _McpOutcome(NamedTuple):
    tools: list[str]
    # a CallToolResult; kept as object so the `is not None` check stays valid
    result: object


async def _mcp_call(token: str, origin: str) -> _McpOutcome:
    headers = {"Authorization": f"Bearer {token}", "Origin": origin}
    async with (
        streamablehttp_client(f"{BASE_URL}/mcp", headers=headers) as (
            read,
            write,
            _,
        ),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        tool_names = [tool.name for tool in tools.tools]
        result = await session.call_tool("answer", {"query": "what is MCP?"})
        return _McpOutcome(tools=tool_names, result=result)


async def _mcp_door() -> None:
    print("\n== MCP DOOR ==")
    settings = get_settings()
    good_token = mint_mcp_token(
        secret=settings.mcp_signing_secret,
        issuer=settings.mcp_token_issuer,
        audience=settings.mcp_token_audience,
        tenant_id="tenant-a",
    )
    try:
        outcome = await _mcp_call(good_token, "https://claude.ai")
        listed = "answer" in outcome.tools
        called = outcome.result is not None
        _check(listed and called, "valid token + origin: listed and called the tool")
    except Exception as exc:
        _check(False, f"valid token + origin should succeed but raised: {exc!r}")

    try:
        await _mcp_call("not-a-real-token", "https://claude.ai")
        _check(False, "bad token should be refused")
    except Exception:
        _check(True, "bad token refused")

    try:
        await _mcp_call(good_token, "https://evil.com")
        _check(False, "disallowed origin should be refused")
    except Exception:
        _check(True, "disallowed origin refused")


async def main() -> int:
    await _owner_door()
    await _visitor_door()
    await _mcp_door()
    failures = [label for passed, label in _results if not passed]
    print(f"\n{len(_results) - len(failures)}/{len(_results)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

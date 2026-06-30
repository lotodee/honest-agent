"""The MCP security middleware on the MOUNTED /mcp app rejects rebinding attempts.

These hit the real app mount (not the middleware in isolation). A rejected request
short-circuits in the middleware before the inner MCP app, so no session manager
is needed; the happy path is proven over real HTTP by scripts/e2e_doors.py.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_mounted_mcp_rejects_disallowed_origin(client: AsyncClient) -> None:
    response = await client.post(
        "/mcp/",
        headers={"Host": "127.0.0.1", "Origin": "https://evil.com"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 403


async def test_mounted_mcp_rejects_forged_host(client: AsyncClient) -> None:
    # DNS-rebinding: a rebound Host the server does not serve under is refused,
    # even with an allowed Origin.
    response = await client.post(
        "/mcp/",
        headers={"Host": "attacker.com", "Origin": "https://claude.ai"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 403

"""Seed the local stack for the Day-1 doors. Idempotent and re-runnable.

Creates the widget_keys table, seeds a public widget key per demo tenant, and
ensures a Supabase owner user per tenant with the tenant in `app_metadata`. Run
with the local Supabase and Postgres up:

    uv run python scripts/seed_local.py
"""

import asyncio

import asyncpg
import httpx

from app.core.settings import Settings, get_settings

DEMO_TENANTS = ("tenant-a", "tenant-b")
WIDGET_KEYS = {
    "wk_tenant_a_public": ("tenant-a", ["tenant-a.example.com", "localhost"]),
    "wk_tenant_b_public": ("tenant-b", ["tenant-b.example.com", "localhost"]),
}
OWNER_USERS = {
    "owner-a@example.com": "tenant-a",
    "owner-b@example.com": "tenant-b",
}
OWNER_PASSWORD = "owner-password-123"  # noqa: S105  local demo user, rotatable

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS widget_keys (
    key TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    allowed_hosts TEXT[] NOT NULL DEFAULT '{}'
)
"""
_UPSERT_KEY = """
INSERT INTO widget_keys (key, tenant_id, allowed_hosts)
VALUES ($1, $2, $3)
ON CONFLICT (key) DO UPDATE
SET tenant_id = EXCLUDED.tenant_id, allowed_hosts = EXCLUDED.allowed_hosts
"""


async def _seed_widget_keys(settings: Settings) -> None:
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as connection:
            await connection.execute(_CREATE_TABLE)
            for key, (tenant_id, hosts) in WIDGET_KEYS.items():
                await connection.execute(_UPSERT_KEY, key, tenant_id, hosts)
    finally:
        await pool.close()
    print(f"seeded {len(WIDGET_KEYS)} widget keys")


async def _ensure_owner_users(settings: Settings) -> None:
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    admin = f"{settings.supabase_url}/auth/v1/admin/users"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        for email, tenant_id in OWNER_USERS.items():
            await _ensure_one_user(client, admin, headers, email, tenant_id)
    print(f"ensured {len(OWNER_USERS)} owner users")


async def _ensure_one_user(
    client: httpx.AsyncClient,
    admin_url: str,
    headers: dict[str, str],
    email: str,
    tenant_id: str,
) -> None:
    created = await client.post(
        admin_url,
        headers=headers,
        json={
            "email": email,
            "password": OWNER_PASSWORD,
            "email_confirm": True,
            "app_metadata": {"tenant_id": tenant_id},
        },
    )
    if created.status_code in (200, 201):
        return
    # Already exists: find the user and update its app_metadata tenant.
    listing = await client.get(
        admin_url, headers=headers, params={"page": 1, "per_page": 200}
    )
    listing.raise_for_status()
    users = listing.json().get("users", [])
    match = next((user for user in users if user.get("email") == email), None)
    if match is None:
        created.raise_for_status()
        return
    updated = await client.put(
        f"{admin_url}/{match['id']}",
        headers=headers,
        json={
            "app_metadata": {"tenant_id": tenant_id},
            "password": OWNER_PASSWORD,
            "email_confirm": True,
        },
    )
    updated.raise_for_status()


async def main() -> None:
    settings = get_settings()
    await _seed_widget_keys(settings)
    await _ensure_owner_users(settings)
    print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())

"""The single shared tenant-scoping dependency. Nothing re-implements this."""

from dataclasses import dataclass

from app.core.errors import TenantAccessError


@dataclass(frozen=True, slots=True)
class Tenant:
    tenant_id: str


async def get_current_tenant() -> Tenant:
    """Resolve and authorize the caller's tenant. The one place scoping lives.

    Every tenant-touching router depends on this; no route re-implements it. The
    real body reads the verified Supabase JWT (or the widget public key for the
    widget path), resolves the tenant, and raises TenantAccessError when the
    requested tenant does not match the caller's claim. It fails closed until
    auth lands, so no route can serve an unscoped tenant by accident.
    """
    raise TenantAccessError(
        "tenant resolution is not wired yet; this is the single scoping seam"
    )

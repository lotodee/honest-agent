"""Tenant routes. The placeholder owner route exercises the Supabase JWT gate."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.tenants.contexts import OwnerRequestContext
from app.tenants.owner_auth import get_owner_context
from app.tenants.schemas import OwnerIdentity

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=OwnerIdentity)
async def read_owner_identity(
    owner: Annotated[OwnerRequestContext, Depends(get_owner_context)],
) -> OwnerIdentity:
    # Placeholder owner route: it only echoes the verified identity so the owner
    # JWT gate is exercisable. Ingestion (what it really gates) is Days 3-4.
    return OwnerIdentity(tenant_id=owner.tenant_id, user_id=owner.user_id)

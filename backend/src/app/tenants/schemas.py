"""API schemas for the tenants domain. Public contract, separate from internals."""

from pydantic import BaseModel


class OwnerIdentity(BaseModel):
    tenant_id: str
    user_id: str

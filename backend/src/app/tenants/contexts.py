"""The three request-context shapes, one per door. They never collapse into one.

Each door produces its own type so the trust model cannot quietly rot into a
single "AuthContext" that papers over the differences. Each carries the tenant
resolved from its OWN credential and nothing the client could forge.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OwnerRequestContext:
    """The logged-in human owner. Tenant comes from the Supabase JWT app_metadata."""

    tenant_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class VisitorRequestContext:
    """An anonymous visitor. Tenant comes from the widget key; only the query rides."""

    tenant_id: str
    query: str


@dataclass(frozen=True, slots=True)
class ExternalCallerContext:
    """An external AI caller. Tenant comes from the external-caller token claim."""

    tenant_id: str

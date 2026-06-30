"""Shared tenant value type.

Day 1 resolves the tenant per door, each from its own credential, into the three
request contexts in `tenants/contexts.py` (owner `app_metadata`, visitor key row,
MCP token claim). This module holds the small shared `Tenant` value type those
seams and the two-tenant test seed use.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tenant:
    tenant_id: str

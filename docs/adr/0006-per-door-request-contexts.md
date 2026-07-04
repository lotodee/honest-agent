# 6. Per-door request contexts (replacing the single get_current_tenant)

Date: 2026-07-04

## Status

Accepted

Supersedes ADR-0004 (the single `get_current_tenant` dependency it named). Promoted
from spec amendment A1.

## Context

Milestone 0 shipped a single shared dependency, `core/deps.py:get_current_tenant`,
as "the one place tenant scoping lives," and ADR-0004 named it as the scoping seam.
The locked spec was then corrected to **three request paths across two trust
domains, each resolving its tenant from its OWN credential**: the owner Supabase
JWT (tenant from `app_metadata`), the visitor public widget key (tenant from the
key row), and the MCP external-caller token (tenant from the token claim). A single
`get_current_tenant(request)` that re-resolves the tenant the same way for every
caller is inconsistent with that model, and in practice it was never wired to a
route — it only ever raised. Keeping it would be dead, misleading scaffolding.

## Decision

Each door resolves its own tenant into its own typed context in
`tenants/contexts.py` — `OwnerRequestContext`, `VisitorRequestContext`,
`ExternalCallerContext` — and `get_current_tenant` is removed. The "single place"
guarantee now holds *per door*: the owner JWT dependency, the visitor gate, and the
MCP middleware are the three scoping seams, and the resolved tenant comes only from
the verified credential, never from request input. There is no single cross-door
tenant dependency and none is to be re-introduced.

## Consequences

- Tenant scoping is enforced once per door, at the credential boundary, not
  re-implemented per route.
- When tenant-DATA routes arrive (Day 2+), each data access is scoped by the tenant
  already on the verified context; a single scoping helper may live *within* a door,
  never one spanning all three.
- `core/deps.py:Tenant` (the small value type) stays; only the cross-door
  dependency was removed.
- Trade-off: three seams instead of one look like more surface, but they match the
  three genuinely different trust domains; collapsing them was the actual risk.

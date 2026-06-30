# 4. One Python service, domain-first layout

Date: 2026-06-30

## Status

Accepted

## Context

The build is one Python service (API + agent + ingestion worker) plus two small
frontends. The module structure must stay readable as features grow and must let
an AI agent hold one capability in context without loading the whole tree.

## Decision

Keep one Python service, not an edge/app split or a second service. Structure it
domain-first, not by file type: each domain (`tenants`, `ingestion`, `agent`,
`retrieval`, `guardrails`, `eval`, `mcp`) owns its router, schemas, service, deps,
and exceptions; `core/` holds settings, logging, observability, the db seam, the
error contract, and the single `get_current_tenant` dependency. Use a `src/`
layout with a mirrored `tests/` tree.

## Consequences

- A change to one capability lives in one package a reviewer or agent can hold whole.
- Tenant scoping is enforced in one place, not re-implemented per route.
- Cloudflare and any second service stay optional and additive, never load-bearing.
- Trade-off: a flat file-type layout looks tidy with two features; it does not survive eight. Domain-first is chosen for the size this reaches.

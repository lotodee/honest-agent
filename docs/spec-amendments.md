# Spec Amendments

Intentional, recorded deviations from the Milestone-0 scaffold and the original
plan. A later day must NOT silently undo these. Each entry says what changed, why,
and what replaces it.

## A1 — `get_current_tenant` removed; tenant scoping is per-door (Day 1)

**What changed.** Milestone 0 shipped a single shared dependency
`core/deps.py:get_current_tenant` as "the one place tenant scoping lives." Day 1
removed it.

**Why.** The locked spec was corrected to **three request paths across two trust
domains, each resolving its tenant from its OWN credential** (owner Supabase JWT →
`app_metadata`; visitor public widget key → key row; MCP external-caller token →
token claim). A single `get_current_tenant(request)` that re-resolves the tenant
the same way for every caller is inconsistent with that model and was never wired
to a route — it only ever raised. Keeping it would be dead, misleading scaffolding.

**What replaces it.** Each door resolves its own tenant into its own typed context
in `tenants/contexts.py` — `OwnerRequestContext`, `VisitorRequestContext`,
`ExternalCallerContext`. The "single place" guarantee now holds *per door*: the
owner JWT dependency, the visitor gate, and the MCP middleware are the three
scoping seams, and the resolved tenant comes only from the verified credential.

**Guidance for later days.** Do NOT re-introduce one shared cross-door
`get_current_tenant`. When tenant-DATA routes arrive (Day 2+), scope each data
access by the tenant already on the verified context, and keep a single scoping
helper *within* a door, not one spanning all three doors. `core/deps.py:Tenant`
(the small value type) stays.

**Reference.** `CLAUDE.md` / `AGENTS.md` coding-standards section; this amendment
supersedes the "ONE shared dependency (`get_current_tenant`)" wording there.

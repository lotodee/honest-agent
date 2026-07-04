# Architecture Decision Records

One significant decision per file, numbered in order. Each ADR has the same shape:
`Status`, `Context`, `Decision`, `Consequences`.

## House rule: ADRs are append-only

An ADR is a point-in-time record. Once it is **Accepted, its `Context` / `Decision`
/ `Consequences` body is never edited** — it is the account of what was decided, and
why, on that date. When a decision changes, do NOT rewrite the old ADR's body:

1. Add a NEW ADR with the new decision (and a `Supersedes ADR-NNNN` line).
2. In the OLD ADR, update ONLY the `Status` block to `Superseded by ADR-NNNN`.

The `Status` block is therefore the single authoritative signal — read it first. A
claim in the body of a superseded ADR describes the world at that ADR's date, not
today. This is deliberately why superseded ADRs are **not** annotated inline at each
stale claim: the `Status` line carries the whole correction, once, in the same place
for every ADR, so there is nothing to re-justify or keep in sync per claim.

Where an ADR's body is still true today, keep following it; where the `Status` says
superseded, follow the successor ADR for the part that changed.

## Current supersede chain

- **ADR-0004** — one Python service, domain-first layout, and the single
  `get_current_tenant` dependency. Superseded by ADR-0006 for the tenant-scoping
  seam only; the one-service / domain-first parts still stand.
- **ADR-0006** — per-door request contexts (replaces `get_current_tenant`). Current.

## Where decisions live

- **Settled architecture decisions:** an ADR here.
- **Transitional amendments:** `docs/spec-amendments.md`, until promoted to an ADR.
- **When an amendment is promoted to an ADR:** update any rules-file citation
  (`CLAUDE.md` / `AGENTS.md`) to point at the ADR, not the amendment.

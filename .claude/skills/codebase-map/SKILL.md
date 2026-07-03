---
name: codebase-map
description: Maintains docs/CODEBASE_MAP.md, a living, terse index of the codebase — every module with a one-line purpose and its key public functions, classes, and types. Update it on every change: a file or symbol created, changed, renamed, moved, or deleted. The map lets anyone or any agent find where things live and what already exists without re-reading the whole tree, which also prevents duplicate implementations. Use after any change that adds, renames, moves, or removes a file, function, class, or type.
---

# Codebase Map

You keep `docs/CODEBASE_MAP.md` accurate. It is a MAP, not documentation: one terse line per thing, enough to know what exists and where, never prose.

## Step 0 — see what changed
Use `git diff` (or `git diff --staged`). Find every file added, changed, renamed, moved, or deleted, and within changed files, every public function, class, or type added, renamed, or removed.

## Update the map
`docs/CODEBASE_MAP.md` is grouped by domain, mirroring `backend/src/app` (core, tenants, ingestion, agent, retrieval, guardrails, eval, mcp) plus any other top-level areas (tests, scripts, migrations, widget, dashboard). For each file: its path, a one-line purpose, and a short bullet list of its public functions, classes, and types, each with a one-line "what it does".
- Added file or symbol: add its entry.
- Renamed or moved: update the path or name; do not leave the old one behind.
- Deleted: remove the entry.
- Behavior changed: fix the one-liner if it is now wrong.
Keep it terse and logically ordered within each group. Private helpers (leading underscore) can be omitted unless they carry a non-obvious rule worth finding later.

## Verdict
PASS only if the map matches the code after this change: nothing in the diff is missing from the map, and nothing in the map points at code that no longer exists. Otherwise fix the map before you are done. A stale map is worse than no map, because it misleads the next reader into trusting it.

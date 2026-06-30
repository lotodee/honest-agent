# 3. mypy strict with the Pydantic plugin

Date: 2026-06-30

## Status

Accepted

## Context

Types are the machine-readable spec the whole build leans on: instant editor
feedback for a human, and a readable contract for an AI agent to generate against.
The type gate must be conventional and defensible, not experimental.

## Decision

Use mypy in strict mode with the Pydantic plugin, configured per Pydantic's
documented settings (`strict = true`, `warn_unused_ignores`, `disallow_any_generics`,
`no_implicit_reexport`, plus the `pydantic-mypy` options). Enforce it in CI. The
only escape hatch is a justified `# type: ignore[code]` with the specific code;
`warn_unused_ignores` turns a stale ignore into a CI error.

## Consequences

- The app cannot construct misconfigured, and wrong data is loud at the boundary.
- mypy is chosen over the faster but still-beta `ty`, because the gate must be conformant and is what Pydantic and FastAPI use.
- mypy runs in CI, not the commit hook, so the commit gate stays under ten seconds.
- Trade-off: a type error can be committed locally and is caught in CI seconds later. Accepted for loop speed.

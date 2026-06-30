# 1. uv for the Python environment

Date: 2026-06-30

## Status

Accepted

## Context

The backend needs reproducible environments across a developer Mac, Linux CI, and
a Docker build. Versions must not drift between machines or over time, and the
install must be fast because the inner loop runs it constantly.

## Decision

Use uv (Astral) for dependency resolution, virtual environments, and installs.
Commit `uv.lock`. Pin Python in `.python-version` and `requires-python`. CI runs
`uv sync --frozen` so a stale lock fails the build instead of silently resolving
something new.

## Consequences

- Byte-identical dependency trees across dev, CI, and Docker from one universal lockfile.
- The pinned lock is the artifact the dependency audit scans; version changes show up as a reviewable lockfile diff.
- One fast Rust binary replaces pip + virtualenv, keeping the feedback loop tight.
- Trade-off: the team standardizes on a newer tool than pip or Poetry. Accepted; there is no prior team standard to honor.

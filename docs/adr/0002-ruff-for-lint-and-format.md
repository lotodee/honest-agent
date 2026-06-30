# 2. Ruff as linter and formatter

Date: 2026-06-30

## Status

Accepted

## Context

The codebase needs correctness, security, and style enforcement that is fast
enough to run on every save and every commit, and deterministic enough that
formatting is never argued about, including by an AI agent.

## Decision

Use Ruff as both linter and formatter. Enable a strict select set:
`E`, `W`, `F`, `I`, `B`, `UP`, `S`, `C4`, `SIM`, `N`, `ASYNC`. The `S` (bandit)
rules guard the PDF-subprocess and tenant code; `ASYNC` catches blocking calls
inside async code. The formatter is Black-compatible, so line length and quotes
are decided by the tool.

## Consequences

- One Rust binary replaces flake8, isort, black, pyupgrade, and bandit-style checks.
- Formatting is deterministic: there is one correct output and the tool produces it.
- The `ASYNC` rules partly enforce the never-block-the-event-loop convention statically.
- Trade-off: opting into a broad rule set surfaces more findings up front. Accepted as the intended floor.

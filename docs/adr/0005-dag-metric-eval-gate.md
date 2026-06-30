# 5. Deterministic DAG metric as the eval gate

Date: 2026-06-30

## Status

Accepted

## Context

The reproducible red-to-green story is a non-negotiable: a bad change must turn
the eval gate red and the fix must turn it green, repeatably, in CI. A gate that
flaps is worse than no gate, because it trains everyone to ignore red.

## Decision

Use DeepEval with the deterministic DAG metric as the CI gate decision, so the
gate's pass/fail is rule-based and does not flap. Run it as its own CI job so its
red or green is a distinct headline artifact. Any LLM-judge metric uses Gemini
(same-family bias documented, cross-family flagged as the production upgrade), and
is not the gate.

## Consequences

- The Day-8 red-to-green is reproducible because the gate decision is deterministic.
- No paid judge is required for the gate, which fits the Gemini-only, cost-disciplined budget.
- The eval layer is marked and separated so the fast inner loop never pays for it.
- Trade-off: a rule-based DAG metric encodes quality criteria explicitly rather than delegating judgment to a model. Accepted; explicitness is the point for a gate.

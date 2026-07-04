# Stub Ledger

Every stub, placeholder, or "for now" in the codebase lives here until its real version ships with a passing test. Nothing is removed from this ledger until its real test is green.

Every review checks the diff against this ledger. A new stub not listed here is a BLOCK (question-pass and senior-pass enforce this). A stub whose close day has passed but is still a stub is a BLOCK.

Rule for every stub: it must (a) sit behind a clean seam, (b) name the day or condition it becomes real, (c) name the real test that will prove the real thing, and (d) FAIL CLOSED — a missing credential or unbuilt dependency raises; it never silently returns fake output in a real run.

| # | Stub | File | Stands in for | Closes on | Real test that proves it | Fail-closed guard |
|---|------|------|---------------|-----------|--------------------------|-------------------|
| 1 | Vision describer (`StubVisionDescriber`) | `ingestion/pdf/router.py` | The live `gemini-3.5-flash` (at location `global`, per ADR-0007) vision description of an image or vector page | Day 4 (ingestion goes live, Vertex provisioned) | A credential-gated integration test renders a real image page and asserts a real, non-placeholder description comes back from Gemini | IMMEDIATE (before Day 4): with no Vertex credential in a non-test run, RAISE, do not return placeholder text |
| 2 | `retrieve` | `retrieval/service.py` | Real tenant-scoped hybrid search in Weaviate | Day 5 | Integration test retrieves seeded chunks from a tenant's shard, and proves it cannot see another tenant's | A missing handle or empty index raises or returns an explicit empty-with-reason, never a fake source |
| 3 | `answer` (grounding + refusal) | `agent/service.py` | Real grounded answer with a faithfulness verdict, and an honest refusal | Day 6 | A grounded question returns a sourced answer; an off-corpus question returns an honest refusal; both asserted against real retrieval | The verdict is always computed from real retrieved chunks, never hard-coded |
| 4 | Rate limiter (`AllowAllRateLimiter`) | `tenants/rate_limit.py` | Real per-key and per-IP rate limiting | Day 11 | Exceeding the limit returns 429; within the limit passes; both asserted | Decide and record fail-open vs fail-closed on a limiter-backend failure |

## Immediate action (not a build day, do it now/next)
Stub #1 currently returns placeholder text when Vertex is absent. That is the one live footgun: if it ever ran in a real ingestion without a credential, it would write placeholder text into a customer's searchable content. Add the fail-closed guard so a missing Vertex credential raises in any non-test run, before Day 4.

## Also not-yet-built (not stubs, just absent — tracked so they are not forgotten)
These are not fakes sitting in the code; they simply do not exist yet and are scheduled. Listed so nothing is silently skipped.
- Embeddings (`gemini-embedding-001` via Vertex, at `output_dimensionality=768` + L2-normalized to fit `chunks.embedding vector(768)`, per ADR-0007) — built and used for real on Day 4 (chunk embedding into Weaviate).
- Generation model (`GoogleModel` via Vertex) — built and used for real on Day 5 (the agent).
- Guardrails (pre-screen, spotlighting, faithfulness) — Day 6.
- Eval gate (three-lane) — Day 7. Dashboard/deploy — Day 9. Widget — Day 10.

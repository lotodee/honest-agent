---
name: spec-review
description: Review implemented code or changes against the LOCKED build spec to make sure nothing has drifted off-plan. Use this when you finish a unit of work, before staging or committing, before opening a PR, or any time you want to confirm a change still matches the locked stack, the locked decisions, the architecture and data flow, the current day's required artifact, and the owner overrides (private demo, Gemini and Vertex only, minimal UI). Run it whenever someone asks to check work against the spec or before declaring a day's artifact done.
---

# Spec Review

You are reviewing a change against the LOCKED build spec for the flagship support-assistant project. The spec is the source of truth. Nothing that drifts off-spec passes. Your job is a clear PASS or CHANGES-REQUIRED verdict with the SPECIFIC deviations and the EXACT fix for each.

## Step 0 — Re-read the source of truth

Always re-read these before judging anything. Do not review from memory.

1. Read `/Users/loto/Desktop/GEN/Planning/BUILD_SPEC_LOCKED.md` in full. This file wins on any conflict.
2. Read the relevant section of `/Users/loto/Desktop/GEN/Planning/flagship_final_plan.md` for the part of the system the change touches (architecture in section 2, decisions in section 1, risks in section 3, the day plan in section 4).

If `BUILD_SPEC_LOCKED.md` and `flagship_final_plan.md` disagree, the LOCKED file wins, because it carries the owner's final adjustments.

## Step 1 — Identify what you are reviewing

Find the change. Use `git diff` (or `git diff --staged`) and read the actual modified files end to end, not just the diff hunks. Establish:

- Which part of the system this touches (ingestion, agent, retrieval, guardrail, eval gate, MCP, dashboard, widget, auth, isolation, observability).
- Which build day this maps to in the Day 1 to Day 12 sequence.

## Step 2 — Check against the LOCKED stack

The change must use the locked tools and only the locked tools for its job. Flag any substitution. The locked stack:

- Agent: PydanticAI on Python and FastAPI, one service (API plus agent plus ingestion worker). Not LangChain, not a second service unless it is the documented additive Cloudflare layer.
- LLM, vision, embeddings: Gemini via Vertex AI. See owner override 2 below. Nothing should call OpenAI, Anthropic, or any other live model for generation, vision, or embeddings.
- Vectors: Weaviate, multi-tenancy enabled, two tenants, hybrid search.
- Relational and auth: Supabase and Postgres, RLS FORCED.
- Eval: DeepEval with the deterministic DAG-metric CI gate, plus one agentic metric, plus an online referenceless scorer on sampled traces.
- Observability: Logfire (OpenTelemetry). Errors: Sentry.
- MCP: remote Streamable-HTTP server as an OAuth 2.1 Resource Server, Origin-validated, verifies an EXTERNAL-CALLER token (a scoped API key or OAuth token that carries the tenant), NOT the owner Supabase login JWT. Validates signature/issuer/audience/expiry, rejects tokens not issued for this server, no token passthrough. Scoped (full OAuth written up, one audience/issuer check demonstrated). On Day 1 the credential is a self-minted signed token verified by a signing secret in env.
- Dashboard: React plus Vite, minimal. Widget: Lit plus Shadow DOM plus Vite library bundle, served from a CDN.
- Object storage: R2 or Supabase Storage, presigned PUT for large uploads.
- Hosting: a warm container (Render, Fly, or Railway) for the Python service.
- CI: GitHub Actions, runs tests plus the eval gate.

## Step 3 — Check against the LOCKED decisions

- Single-tenant-excellent: exactly two tenants plus a passing isolation test, scale path documented not operated. Do not let the change try to operate tenant tiering, cold-tiering, or thousands of tenants.
- One Python service. The visitor edge gate (widget-key + Origin allowlist + rate limit + sanitize) is in-app FastAPI middleware (Option B, owner-decided 2026-06-30); Cloudflare is optional and additive, never load-bearing, documented as the production move and the ingestion-queue scale-out target.
- Three request paths across two trust domains, each resolving tenant from its own credential: owner Supabase JWT (login/ingestion), visitor public widget-key + Origin allowlist (no login), external-caller token for the MCP. Never reuse the owner JWT as the MCP credential.
- Honesty verdict is fused into the answer capability (every answer returns {answer, verdict}); it is never an optional tool. Core capabilities are plain functions exposed via two thin adapters (in-process for the widget, MCP tool for external callers).
- Key storage: widget keys are public identifiers in Postgres linked to tenant + allowed origins (not hashed); the MCP credential is a signing secret in env on Day 1, moving to a hashed-keys table later.
- Scoped MCP. Full OAuth authorization server is documented in prose plus one demonstrated audience and issuer check, not built.
- Dev-docs seed corpus.
- Logfire for online eval (single surface).
- DAG-metric gate for the reproducible red-to-green story, Gemini judge for any LLM-judge metric.
- Self-render vision for image pages (rasterize and describe), not direct-PDF vision.

## Step 4 — Check against the architecture and data flow

Confirm the change respects the data flow in section 2.2 of the plan. Common drifts to catch:

- Large uploads must go direct to object storage via presigned PUT, never stream through the API process.
- Ingestion is async and off the request path: queue, content-hash (SHA-256) idempotency, deterministic UUIDv5 upsert, per-document status rows, DLQ with a reason on failure.
- PDF parsing runs in a timeout-bounded subprocess so a poison file cannot crash the worker.
- OCR is gated behind scanned-page heuristics. Vision runs only on image-bearing or vector-heavy pages, after downsample and content-hash dedupe.
- Heavy ML imports stay off the request path (ingestion worker only).
- The API is a Backend-for-Frontend: the model and Vertex credentials never reach the browser. The bundle holds only the public widget key.
- Retrieval is tenant-scoped hybrid search inside one tenant only. Isolation is enforced by the Weaviate shard boundary and by Postgres RLS.
- The agent returns a typed output: a grounded answer with sources, or an honest refusal verdict.
- Widget streams via fetch-based streaming with a Bearer header, not native EventSource.
- One Logfire trace per run, errors to Sentry.

## Step 5 — Check against the current day's required artifact and its non-negotiables

Map the change to its build day and confirm it actually produces that day's artifact. The non-negotiable spine:

- Day 2: a test proves tenant A cannot read OR write tenant B, in both Postgres and Weaviate. RLS FORCED, app role non-owner and non-BYPASSRLS, WITH CHECK on writes, app_metadata-based policies, tenant_id indexed.
- Day 3: a scanned PDF becomes searchable text, a diagram-only page is retrievable by its described content, and a poison PDF lands in the DLQ with a reason instead of crashing the worker.
- Day 8: a real reproducible red-to-green on GitHub Actions, driven by the deterministic DAG metric so it does not flap.
- Day 9: the system is deployed and reachable on a hosted URL, dashboard live, two tenants seeded.

If the change claims a day's artifact but does not fully deliver the artifact and its non-negotiables, that is CHANGES-REQUIRED.

## Step 6 — Verify the owner overrides are honored

These OVERRIDE everything else. Any violation is an automatic CHANGES-REQUIRED.

1. Demo is private. Deploy to a hosted URL, shareable on request. No public front door, no public promotion. Build-in-public is the messy process narrative, not a public product launch.
2. LLM budget is Gemini via Vertex AI free credits ONLY. Generation, vision, and embeddings all run on Vertex and Gemini. The multi-provider abstraction is still built as a real fallback seam, but Gemini is the only live model. The CI gate uses the deterministic DAG metric (no paid judge). Any LLM-judge metric uses Gemini, with same-family bias documented and cross-family flagged as the production upgrade. Cost discipline must be present where relevant: prompt caching, content-hash dedupe before any vision call, embedding cache, gated OCR.
3. UI is minimal and product-only: upload, status, results, trace link. Red-to-green is shown via the real GitHub Actions run plus build-in-public posts, NOT a custom eval-visualization UI. Reject any dashboard scope creep.

## Step 7 — Verdict

Produce one of two verdicts.

**PASS** only if the change honors the locked stack, the locked decisions, the architecture and data flow, the current day's artifact and non-negotiables, and all three owner overrides. Briefly name what you confirmed.

**CHANGES-REQUIRED** if anything drifts. For each deviation, give:

- The specific deviation (file and line where possible).
- Which locked rule, decision, override, or artifact it violates.
- The exact fix to bring it back on-spec.

Order the list with override and non-negotiable violations first. Be concrete, not vague. Nothing off-spec passes. Do not soften the verdict to be polite.

# Flagship Build Spec — LOCKED & APPROVED

**Status:** Approved by Dotun. This file is the build's source of truth. Full detail (architecture, data flow, risk register, citations) lives in `flagship_final_plan.md`. Where the two differ, THIS file wins, because it carries the owner's final adjustments.

## Product, one line
A multi-tenant embeddable AI support assistant. An owner feeds it their content (PDFs including scanned/image PDFs, plus a small site crawl), drops one script tag on their site, and the widget answers visitors grounded only in that owner's content, refuses with an honesty verdict when it cannot ground an answer, and resists prompt injection. The reliability/evaluation layer is the product.

## Owner adjustments that OVERRIDE the final plan
1. **Demo is private.** Deploy to a hosted URL, share to a recruiter on request. Do NOT promote a public front door. The public narrative stays build-in-public: the messy process, the failing evals, the red CI, the fixes.
2. **LLM budget = Gemini via Vertex AI free credits ONLY.** Generation, vision (image PDFs), and embeddings all run on Vertex/Gemini. The multi-provider abstraction is still built (engineering signal + a real fallback seam), but Gemini is the live model and we state that plainly. The CI gate uses DeepEval's deterministic DAG metric (rule-based, no paid judge, does not flap). Any LLM-judge metric uses Gemini, with same-family bias documented honestly and cross-family flagged as the production upgrade. Show cost discipline: prompt caching, content-hash dedupe before any vision call, embedding cache, gated OCR. Cost and latency are handled, not the centerpiece. **Cost posture:** the only credit card needed anywhere is the Google Cloud billing card that activates the Vertex free-trial credit, and that credit is spent only on Gemini API calls. Hosting (Render/Fly free + keep-alive ping) and every other service (Supabase, Sentry, Logfire, GitHub, Weaviate self-host via Docker) stay free and card-free.
3. **UI is minimal.** The dashboard is product-only: upload, status, results, trace link. Red→green is shown via the real GitHub Actions CI run plus the build-in-public posts, NOT a custom eval-visualization UI.

## Locked stack
- Agent: PydanticAI on Python/FastAPI (one service: API + agent + ingestion worker)
- LLM + vision + embeddings: Gemini via the **Vertex AI API** (free credits). Vertex is used ONLY as the Gemini API, never for hosting, so hosting compute does not consume the Gemini credits.
- Vectors: Weaviate (multi-tenancy enabled, two tenants, hybrid search)
- Relational + auth: Supabase / Postgres (RLS forced)
- Eval: DeepEval (DAG-metric CI gate) + one agentic metric; online referenceless scorer on sampled traces
- Observability: Logfire (OpenTelemetry). Errors: Sentry
- MCP: remote Streamable-HTTP server, Origin-validated, bearer-token verified (scoped; full OAuth hardening written up, one check demonstrated)
- Dashboard: React + Vite (minimal). Widget: Lit + Shadow DOM + Vite library bundle, served from a CDN
- Object storage: R2 or Supabase Storage (presigned PUT for large uploads)
- Hosting: the Python service runs on a **free tier (Render free, or Fly)**, kept warm with a **free keep-alive ping** (UptimeRobot, cron-job.org, or a GitHub Actions cron hitting `/health` every ~10-12 min, under Render's 15-min idle sleep). **NOT hosted on Google Cloud**, so hosting never draws down the Vertex/Gemini credits. Cold starts are small anyway because models are remote (Vertex API), not local weights in the container.
- CI: GitHub Actions (runs tests + the eval gate)

## Locked decisions
Single-tenant-excellent (two tenants + a passing isolation test, scale path documented); one Python service (Cloudflare optional/additive, not load-bearing); scoped MCP; dev-docs seed corpus; Logfire for online eval; DAG-metric gate + Gemini judge; self-render vision for image pages.

## Standards (enforced on every commit, by skill)
Tests beside the code (unit, integration, the eval suite), all green in CI. Clean conventional architecture. DRY and reusable. Typed Python end to end. Minimal comments (a non-obvious WHY only, never narrate; no comment rot). No dead code. Real error handling. Nothing mediocre. Two Claude Code skills run on the work: a code-review-against-this-spec pass and a senior-engineering-standards pass.

## Build sequence (12 working days, riskiest spikes first)
- **Day 1** — Foundations + MCP spike (repo, CI skeleton, typed FastAPI, BFF secrets, Supabase auth, working remote Origin+token MCP server).
- **Day 2** — Tenant isolation, proven: RLS forced + Weaviate two tenants + a test that tenant A cannot read/write tenant B. **(non-negotiable)**
- **Day 3** — OCR/vision PDF spike: native text → gated OCR → Gemini-vision for image pages; poison PDFs parsed in a subprocess → DLQ. **(non-negotiable)**
- **Day 4** — Ingestion end-to-end (presigned upload, queue, idempotent upsert, status, DLQ, backpressure).
- **Day 5** — Agent + grounded answer (PydanticAI, tenant-scoped hybrid retrieval, Gemini behind the interface, typed verdict).
- **Day 6** — Refusal + prompt-injection guardrail (honest refusal; pre-screen + spotlighting; blocks "ignore previous instructions").
- **Day 7** — Observability + the non-flapping eval gate (Logfire, Sentry, DeepEval golden set, DAG gate in CI).
- **Day 8** — Red→green (push bad change → CI red → fix → green, reproducibly) + agentic metric + online scorer. **(non-negotiable: reproducible red→green)**
- **Day 9** — Minimal dashboard + deploy to a hosted URL, seed two tenants (dev docs), kept private/shareable. **(non-negotiable: deployed and reachable)**
- **Day 10** — Embeddable Lit/Shadow-DOM widget (isolated, fetch-streaming, CDN bundle, works on three host pages without breaking them).
- **Day 11** — Injection demo on the live URL (refuse + resist) + adversarial block-rate + widget telemetry + flow polish.
- **Day 12** — Hardening + README essay with the week's real numbers + MCP OAuth and scale-seam write-ups + architecture diagram + a 60-90s clip.

**Spine to protect:** Day-2 isolation test, Day-3 poison-PDF survival, Day-8 reproducible red→green, Day-9 deployed. If a day slips, Day-11 telemetry is the buffer.

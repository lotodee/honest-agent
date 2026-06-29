# Flagship App — End-to-End Flow

Distilled faithfully from `BUILD_SPEC_LOCKED.md` (the approved source of truth; its owner adjustments override) and `flagship_final_plan.md` (detailed architecture, especially the data-flow section). Nothing here is invented; where the two docs differ, the locked spec wins. Open decisions are flagged at the end.

---

## 1. What the product IS (one line) and its tenancy posture

It is an embeddable AI support assistant where the reliability/evaluation layer is the product. An owner feeds it their content (PDFs, including scanned/image PDFs, plus a small site crawl), drops one script tag on their site, and the widget answers visitors grounded only in that owner's content, refuses with an honesty verdict when it cannot ground an answer, and resists prompt injection.

Tenancy posture: it is built single-tenant-excellent with two seeded tenants, NOT full multi-tenancy. Weaviate multi-tenancy is enabled (one config flag, the right design) and operated for exactly two tenants; Postgres RLS is written and forced; a passing isolation test proves tenant A cannot read or write tenant B; the scale story (shard ceilings, tiering, backups) is written up and cited rather than operated. The senior signal targeted is "I understand tenant data isolation and its failure modes," not "I run thousands of tenants." The locked spec phrases this as "single-tenant-excellent (two tenants + a passing isolation test, scale path documented)."

---

## 2. OWNER / SETUP flow (onboarding and ingestion)

How a site owner onboards and feeds content:

1. The owner signs up. Supabase provides auth and issues JWTs. Postgres/Supabase holds tenants, users, documents, and configs, with RLS forced.
2. From the minimal dashboard (product-only: upload, status, results, trace link), the owner either uploads a PDF (including scanned/image PDFs) or starts a small site crawl.
3. Large uploads go directly to object storage (R2 or Supabase Storage) via a presigned PUT, so the file never streams through the API process.

How content gets ingested (queue-backed, idempotent, DLQ-protected, off the request path):

4. An ingestion job is enqueued on a real async queue. In-process with durable rows is acceptable for the demo; the README notes the production swap to Cloudflare Queues or SQS. The message carries a reference, not the file itself.
5. The ingestion worker pulls the file from object storage and computes a SHA-256 content hash for idempotency.
6. The worker runs a per-page router:
   - Native text extraction first.
   - Gated OCR only for pages that pass scanned-page heuristics (image-coverage ratio, empty text, GlyphlessFont prior-OCR signal). OCR is gated because it is roughly 1000x slower than native extraction.
   - Rasterize-and-vision-describe only for image-bearing or vector-heavy pages (`get_images()` silently misses vector graphics, so vector-heavy pages must be rasterized), after downsampling (to under 2000px) and content-hash dedupe so identical pages are described once before any paid vision call.
7. Crash isolation: PDF parsing runs in a timeout-bounded subprocess, because poison/malformed PDFs can segfault the MuPDF C library, which is a process crash, not a catchable Python exception. Encrypted (`needs_pass`) and malformed files are detected explicitly.
8. Chunks are embedded and upserted into the tenant's own Weaviate shard using a deterministic UUIDv5, so re-ingesting a document updates rather than duplicates.
9. Per-document status (queued, processing, done, failed) is written to Postgres for the dashboard.
10. A poison file that exhausts its retries lands in a dead-letter queue and is surfaced as `failed` with a reason, never silently dropped. Backpressure is applied on downstream 429s.

Cost discipline runs throughout: content-hash dedupe before any vision call, gated OCR, embedding cache, and prompt caching elsewhere. Vision, OCR, and embeddings all run on Gemini via Vertex AI (see section 6).

---

## 3. VISITOR / QUERY flow (question to streamed grounded answer or refusal)

1. The widget POSTs the visitor's question to the API with the tenant's public widget key. The API is a Backend-for-Frontend (BFF): the model API key never reaches the browser; the bundle holds only the public widget key.
2. The API screens the input for prompt injection: a lightweight pre-screen (a harmlessness screen) plus spotlighting/delimiting of retrieved content, plus a system prompt that forbids executing instructions found in retrieved documents. This is what blocks "ignore previous instructions" rather than obeying it.
3. The API runs the PydanticAI agent with typed deps that carry the tenant's Weaviate handle.
4. The agent's `retrieve` tool runs a hybrid search inside that tenant only. Tenant isolation is enforced by the Weaviate shard boundary and by RLS in the relational layer.
5. The agent drafts an answer; the faithfulness guardrail grades the answer against the retrieved chunks. The typed output returns either a grounded answer with sources/citations or an honest refusal verdict when it cannot ground the answer.
6. The whole run is one Logfire (OpenTelemetry) trace; errors go to Sentry.
7. The response streams back to the widget via fetch-based streaming with a Bearer header (NOT native EventSource, which cannot send an auth header cross-origin).

---

## 4. EVALUATION flow (offline CI gate plus online scorer)

Offline CI gate (the spine, the red-to-green story):

1. A golden set of question / expected-answer / expected-source rows is scored by DeepEval, covering faithfulness, answer relevancy, and contextual precision/recall, plus one agentic metric (Tool Correctness or Task Completion).
2. The pass/fail gate decision uses DeepEval's deterministic DAG metric (rule-based, no paid judge) so the gate does not flap. Temperature 0 does not guarantee determinism and LLM-as-judge metrics like G-Eval are explicitly non-deterministic, so the headline gate decision is DAG-based to stay reproducible. Thresholds are set with margin; the model version is pinned.
3. `deepeval test run` fails the build below threshold, in GitHub Actions CI.
4. Red-to-green: a deliberately bad change is pushed, CI goes red reproducibly (because the gate is DAG-based), then the fix makes it green. The red GitHub Actions run followed by the green one is the headline artifact; red-to-green is shown via the real CI run plus build-in-public posts, NOT a custom eval-visualization UI.
5. Judge pairing: any LLM-judge metric uses Gemini, with same-family bias documented honestly and cross-family flagged as the production upgrade. (The final plan recommends cross-family judging, e.g. generate with one family and judge with another; the locked spec constrains the live judge to Gemini given the Vertex-only budget, and the locked spec wins.)

Online scorer (on sampled traces):

6. A referenceless faithfulness scorer runs on sampled demo traces in Logfire, with scores attached to the trace. It is the same metric family as the offline gate, giving the "same metric logic runs offline and online" signal. It is surfaced on the trace, not built as a full production sampling pipeline with multi-surface reconciliation.

---

## 5. MCP flow (remote, Origin- and token-verified tool)

1. A remote Streamable-HTTP MCP server runs on the same Python service, exposed at a single `/mcp` endpoint.
2. It is Origin-validated and bearer-token-verified, using the same Supabase JWT the API uses, with issuer and audience checked.
3. It exposes the answer-plus-verdict tool (the agent's grounded-answer-or-refusal capability as an MCP tool, so it is a real remote tool, not a stdio toy).
4. Full OAuth 2.1 Resource Server hardening (RFC 9728 Protected Resource Metadata, audience validation, no token passthrough, confused-deputy avoidance) is written up in the README as "how this hardens for production," with one piece demonstrated (audience/issuer validation on the token). The full authorization-server dance is deliberately not built, because the research shows it is a multi-week effort that a real team abandoned.

---

## 6. Observability, errors, and the LLM constraint

- Observability: Logfire on OpenTelemetry; one trace per run, showing a full span tree.
- Errors: Sentry on the backend, plus an isolated Sentry BrowserClient for the widget.
- LLM constraint: Gemini via the Vertex AI API only, on free credits. Generation, vision (image PDFs), and embeddings all run on Vertex/Gemini. A multi-provider abstraction is still built (engineering signal and a real fallback seam), but Gemini is the live model and that is stated plainly. Vertex is used ONLY as the Gemini API, never for hosting, so hosting compute does not consume the Gemini credits.
- Cost posture: the only credit card needed anywhere is the Google Cloud billing card that activates the Vertex free-trial credit, and that credit is spent only on Gemini API calls. Hosting and every other service (Supabase, Sentry, Logfire, GitHub, Weaviate self-hosted via Docker) stay free and card-free.

---

## 7. Deployment and the widget embed

Deployment / hosting:

1. The single Python service (API + agent + ingestion worker) runs on a free tier (Render free, or Fly), kept warm with a free keep-alive ping (UptimeRobot, cron-job.org, or a GitHub Actions cron hitting `/health` every ~10-12 minutes, under Render's 15-minute idle sleep). It is NOT hosted on Google Cloud, so hosting never draws down the Vertex/Gemini credits. Cold starts are small because models are remote (Vertex API), not local weights in the container; heavy ML imports are kept off the request path (ingestion worker only).
2. The demo is private: deployed to a hosted URL and shared to a recruiter on request. There is no public front door promoted; the public narrative stays build-in-public (the messy process, failing evals, red CI, the fixes). API, agent, Weaviate, and Postgres are deployed to the hosted environment, and two demo tenants are seeded with real public content (developer docs is the recommended corpus).

Widget embed:

3. The widget is built with Lit + Shadow DOM as a single self-contained Vite library-mode bundle (Lit bundled in), served from a CDN with a fingerprinted filename, immutable cache, and `Access-Control-Allow-Origin: *`.
4. The owner pastes one async script tag.
5. Isolation safeguards: `customElements.define` is guarded against double-define; the shadow root uses `:host { all: initial }` so host-page font/color/line-height does not leak in; the element attaches to `document.body` with `position: fixed`; CSS is injected as a string, not via `<link>`; it is tested on three very different host pages without breaking them; the host CSP allowlist requirement is documented.
6. Cross-origin streaming uses fetch-based streaming with a Bearer header, reflecting the validated Origin (not wildcard) when credentials are needed, and handles the OPTIONS preflight.

---

## Open decisions the docs leave (or where the two docs diverge)

These are recorded as the source of truth currently stands:

- Judge pairing divergence: the final plan recommends cross-family judging (generate with one family, judge with another, e.g. Claude/GPT or Gemini). The locked spec overrides this to "any LLM-judge metric uses Gemini" because the budget is Gemini-via-Vertex only, with same-family bias documented and cross-family flagged as the production upgrade. The locked spec wins; this is settled, not open, but the divergence is noted.
- Edge/app split: resolved to one Python service plus CDN widget, with Cloudflare optional/additive and not load-bearing. Adding a thin Cloudflare Worker front is only a buffer-day option if Cloudflare is specifically wanted on the resume.
- Multi-tenant scope: settled at single-tenant-excellent with two tenants. The owner could seed more tenants if a target employer is explicitly a multi-tenant-vector-DB shop, but the tiering is not operated.
- Domain / seed corpus: recommended as developer docs (makes hybrid retrieval visibly necessary; the GitHub audience is developers). Switch to a regulated corpus only if a specific fintech/legal/health employer is the target; the architecture does not change.
- Object storage choice: stated as "R2 or Supabase Storage" (presigned PUT for large uploads) — either is acceptable, not pinned to one.
- Hosting target: stated as "Render free, or Fly" — either is acceptable, not pinned to one.
- Keep-alive mechanism: stated as UptimeRobot, cron-job.org, or a GitHub Actions cron — any of the three.
- Queue implementation for the demo: a real async queue, "in-process with durable rows is acceptable for the demo," with the production swap to Cloudflare Queues or SQS noted in the README.
- Agentic metric choice: "Tool Correctness or Task Completion" — one of the two, not pinned.

Note on embeddings: the locked spec states embeddings run on Gemini via Vertex (the source of truth). The final plan's section 1.6 mentions a "bring-your-own embeddings (OpenAI or Voyage)" idea carried from v2's open decision, but the locked spec overrides this to Vertex/Gemini for embeddings, and the locked spec wins.

# Flagship Final Plan — The Honest Support Agent (right-sized to 2 weeks)

**Prepared by:** Principal engineer, critical design review
**Date:** 2026-06-28
**For:** Dotun Loto. Goal: a flagship that makes a senior engineer or hiring manager want to hire him, and that is genuinely FINISHED and polished in about two weeks.
**Status:** This is the final plan. It reads `flagship_master_plan_v2.md` (the doc-backed architecture), `flagship_master_plan.md`, and `build_plan_two_projects.md`, and it overrides v2 where v2's ambition fights the finish-in-two-weeks goal. Where I override, I say so and why.

Voice rules carried through: plain English, short lines, concrete over adjectives, no fabricated metrics, no em dashes.

---

## 0. THE ONE THING THAT CHANGED, AND WHY

v2 is an excellent architecture document. It is also a 24-to-30-day plan wearing a 2-week plan's clothes. The tell is in v2's own section 4: "Honest total: 24 to 30 working days for the full flagship." Two weeks is the agreed target. One week reads as vibe-coded with no rigor. So the real decision is not "what is the best possible system" but "what is the most senior-credible system that is genuinely DONE in ten to twelve working days, with a recruiter-clickable live demo at the center."

The override that drives everything else: **build single-tenant-excellent with a clean, demonstrated, designed-to-scale seam, not full multi-tenancy.** v2 makes multi-tenancy the headline ("multi-tenant, embeddable"). I am moving it from "built and operating at scale" to "built for exactly two tenants, isolation proven by a passing test, with the scale path documented and cited." This is not a retreat from the senior bar. It is the difference between a system that is finished and one that is impressive-but-unfinished, and unfinished-but-ambitious reads worse than tight-and-polished to the exact audience we are trying to impress.

Everything below follows from that one call plus five supporting ones.

---

## 1. DECISIONS REVISITED

Each row: the v2 choice, the alternative, the final call, and why it serves "finished and hireable in two weeks." OVERRIDE means I changed v2.

### 1.1 Multi-tenancy: full multi-tenant vs single-tenant-excellent with a scale seam → **OVERRIDE**

- **v2 said:** full multi-tenancy is the headline. Weaviate native multi-tenancy (one shard per tenant), Postgres RLS on every table, per-tenant rate limits, per-tenant cache tags, tenant cold-tiering in phase 5.
- **Alternative:** single-tenant-excellent. Two seeded tenants to prove isolation, RLS written and tested, Weaviate multi-tenancy enabled with two tenants, and the scale story (shard ceilings, tiering, backups) written up and cited rather than operated.
- **Final call: single-tenant-excellent with two tenants and a proven isolation seam.**
- **Why:** the senior signal of multi-tenancy is "I understand tenant data isolation and its failure modes," not "I am running 50,000 tenants." You get the full signal from two tenants plus one test that proves tenant A cannot read tenant B, plus a README section that names the real ceilings. The research says the operational depth of true multi-tenancy is a trap for a short build: Weaviate's active-shard ceiling is bounded by the Linux open-file limit and needs an ACTIVE/INACTIVE/OFFLOADED deactivation strategy planned "from day one, not bolted on later" (https://docs.weaviate.io/weaviate/concepts/data, https://docs.weaviate.io/weaviate/starter-guides/managing-resources/tenant-states); auto-tenant-activation has an open multi-node bug (https://github.com/weaviate/weaviate/issues/8651); backups silently exclude non-ACTIVE tenants (https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy). None of that buys interview signal in two weeks; all of it can eat days. Build the seam, prove it, cite the ceiling, move on.
- **What stays from v2:** Weaviate multi-tenancy is still ENABLED (it is one config flag and it is the right design). RLS is still written and FORCED. The point is we operate two tenants, not that we pretend to operate thousands.

### 1.2 Edge/app split: Cloudflare Workers edge + Python app plane vs one container service → **OVERRIDE (simplify)**

- **v2 said:** three planes. Cloudflare Workers edge (widget serving, API proxy, per-tenant rate limit, queue dispatch), a separate Python application plane, plus the data plane.
- **Alternative:** one Python container service (FastAPI) that does everything except static widget serving, which goes on a CDN. Keep a queue, but an in-process or lightweight one, not a Cloudflare Worker consumer dispatching to Python.
- **Final call: one Python service for API + agent + ingestion worker, static widget bundle served from a CDN with immutable cache and CORS, a real async queue for ingestion. Cloudflare optional and additive, not load-bearing.**
- **Why:** the edge/app split in v2 exists to respect Worker CPU and memory caps (5 minutes, 128 MB), which is a real constraint (https://developers.cloudflare.com/workers/platform/limits/). But the split also doubles the number of deploy targets, adds a Worker-to-Python dispatch hop, and adds the Cloudflare Queues at-least-once and batch-retry gotchas to the critical path (a single failed message retries the whole batch unless each message is acked, https://developers.cloudflare.com/queues/configuration/batching-retries/; delivery is never exactly-once, https://developers.cloudflare.com/queues/reference/delivery-guarantees/). In two weeks, two deploy targets that each have to be perfect is a finishing risk. One well-built Python service with a clean queue is more finishable and just as defensible. The async ingestion story (queue, DLQ, idempotency, backpressure) survives intact; it just runs in or beside the Python service instead of across a Worker boundary.
- **What stays from v2:** the queue-backed, idempotent, DLQ-protected ingestion design. The reasoning about why ingestion is async and off the request path. We keep all of it; we just do not split it across Cloudflare.
- **Honest note for the README:** state that the production scale-out is "move the queue to Cloudflare Queues or SQS and front the API with a Worker," and that we kept it single-service for the demo. That is a stronger statement than a half-built split.

### 1.3 MCP server: OAuth-secured remote MCP vs scoped or deferred → **OVERRIDE (re-scope, do not cut)**

- **v2 said:** OAuth 2.1 Resource Server MCP targeting the 2025-11-25 spec: RFC 9728 Protected Resource Metadata, audience validation, PKCE, Supabase as the authorization server, dynamic client registration, Origin validation.
- **Alternative A:** drop MCP entirely. **Alternative B:** ship a Streamable-HTTP MCP server with a single bearer-token check and Origin validation, and write up the full OAuth design without building the whole authorization-server dance.
- **Final call: Alternative B. Ship a real remote (Streamable-HTTP) MCP server with Origin validation and a verified bearer token (the same Supabase JWT the API uses), exposing the answer-plus-verdict tool. Write the full OAuth 2.1 Resource Server design (audience validation, RFC 9728, no token passthrough, confused-deputy) into the README as "how this hardens for production," and demonstrate one piece of it (audience/issuer validation on the token).**
- **Why:** this is the single biggest finishability risk in v2. The research is blunt. A team at Upstash/Context7 spent "a couple weeks" just understanding the MCP OAuth flow, "initially built a complete OAuth 2.1 implementation from scratch and then threw it away," and concluded "we're not in the business of running OAuth servers" (https://upstash.com/blog/mcp-oauth-implementation). The 2025-11-25 spec stacks five RFCs and explicitly implements "a selected subset" of each (https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization). Client ID Metadata Documents add an SSRF surface on the authorization server. Supabase can be the AS but, per its own community discussions, does not yet ship CIMD (https://github.com/orgs/supabase/discussions/41695), so you would be on the spec's backwards-compat path anyway. Building the full AS dance in two weeks risks the whole flagship slipping. A working remote MCP server with token verification and Origin validation still demonstrates the senior signal (a real remote tool, not a stdio toy), and the written OAuth hardening plan demonstrates that he knows exactly what production requires. That combination is honest and it finishes.
- **What stays:** the MCP server is real, remote, Streamable-HTTP, Origin-validated, token-checked, and exposes the agent. The OAuth depth lives in prose plus one demonstrated check, not in a fragile half-built authorization server.

### 1.4 Online eval: live sampled production eval vs deferred-with-mechanism-shown → **OVERRIDE (re-scope)**

- **v2 said:** online sampled eval on live traffic with referenceless metrics, two competing surfaces (Logfire live-evals vs Confident AI), reconciled in a section.
- **Alternative:** keep the offline CI gate as the non-negotiable, and show online eval as a working mechanism on a sample of seeded demo traffic with one screenshot, described as "this is how it runs on production sampling."
- **Final call: offline CI gate is the spine and ships fully. Online eval ships as a working referenceless scorer that runs on sampled traces in the live demo, surfaced on the trace, not as a full production sampling pipeline with reconciliation.**
- **Why:** the closed loop (production traces become datasets become the next gate) is a beautiful story but it needs production traffic to be real, and we will not have production traffic in two weeks. A working referenceless faithfulness scorer attached to demo traces gives the same "the same metric logic runs offline and online" signal without the multi-surface reconciliation that v2 itself flagged as an open decision. Pick Logfire live-evals for one surface (the traces already live there) and stop.

### 1.5 Vision-per-image-PDF: build it vs gate-and-cache it carefully → **KEEP, harden**

- **v2 said:** detect, then route. Native text first, OCR only when needed, vision-describe only image-bearing pages, dedupe by content hash.
- **Final call: keep exactly this, and harden it with the specific cost, latency, and crash defenses the research surfaced.** This is the right design and it is a genuine senior signal (most portfolios skip image PDFs entirely).
- **Why and the hardening (all cited in the risk register):** OCR is about 1000x slower than native extraction, per PyMuPDF's own docs, so it must be gated (https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html). There is no failsafe scanned-page detector, only heuristics like image-coverage ratio and the GlyphlessFont signal for prior OCR layers (https://github.com/pymupdf/PyMuPDF/discussions/1653). `get_images()` silently misses vector graphics, so vector-heavy pages must be rasterized (https://pymupdf.readthedocs.io/en/latest/recipes-images.html). Poison PDFs can segfault the MuPDF C library, which is a process crash not a catchable exception, so PDF parsing runs in a timeout-bounded subprocess (https://github.com/pymupdf/PyMuPDF/issues/4533). Vision cost is real and dimension-driven, with a hard 2000px-per-image rule above 20 images per request, so we downsample and content-hash-dedupe pages before any paid vision call (https://platform.claude.com/docs/en/build-with-claude/vision). This is the area where the build looks most senior, so it earns its two days.

### 1.6 Embeddings, vector store, and the rest → **KEEP**

- Weaviate (multi-tenancy enabled, hybrid search), Postgres/Supabase (RLS, auth), PydanticAI (typed agent, typed honesty verdict, MCP host), DeepEval (offline gate), Logfire (tracing plus evals), Sentry (errors plus isolated widget client), Lit plus Shadow DOM widget: all confirmed in role, each maps to one job. v2's tool reconciliation (drop Langfuse for Logfire, Analytics Engine over PostHog, Workers Static Assets over Pages) is sound and I keep it where Cloudflare stays in scope. Bring-your-own embeddings (OpenAI or Voyage) for provider control, per v2's open decision 2.

---

## 2. FINAL ARCHITECTURE (right-sized to two weeks)

### 2.1 The product in one sentence

A site owner signs up, feeds the system their content (uploaded PDFs including image and scanned PDFs, plus a small site crawl), and drops one script tag on their site. The embedded widget answers their visitors' questions grounded only in that owner's content, refuses and shows an honesty verdict when it cannot ground an answer, and resists prompt-injection attempts from visitors. Two tenants prove isolation. Every answer is traced, evaluated offline as a CI gate and online on sampled traces, and the agent is also exposed as a remote MCP tool. A live, hosted, seeded public demo is the front door.

The sentence Dotun says out loud:

> "It is an embeddable support assistant with the reliability layer as the product. Content is ingested through a queue-backed, idempotent pipeline that handles image and scanned PDFs with a gated OCR-and-vision path and a dead-letter queue for poison files. Each tenant's content is isolated in its own Weaviate shard and behind Postgres row-level security, and I have a test that proves tenant A cannot read tenant B. The agent does hybrid retrieval inside the tenant, grades its own answer for faithfulness before returning, refuses when it cannot ground, and screens visitor input for prompt injection. The same eval metrics run as a CI merge gate offline and on sampled traces online, with a deterministic decision tree so the gate does not flap. Everything is traced on OpenTelemetry through Logfire, errors go to Sentry, and the agent is exposed as a remote MCP server. There is a live hosted demo you can try."

Every clause is built, demonstrated, and finished. Nothing is aspirational.

### 2.2 Components and data flow

**Two planes, one trace.** A single Python service (FastAPI plus PydanticAI) is the application: it serves the API, runs the agent, and runs the ingestion worker. A static widget bundle is served from a CDN. The data plane is Weaviate (vectors, two tenants) plus Postgres/Supabase (tenants, users, configs, auth, RLS) plus object storage for raw uploads.

**Ingestion path:**
1. Owner uploads a PDF or starts a small crawl from the dashboard. Large uploads go direct to object storage via a presigned PUT so the file never streams through the API process.
2. An ingestion job is enqueued (a real async queue; in-process with durable rows is acceptable for the demo, with the README noting the swap to Cloudflare Queues or SQS for production). The message carries a reference, not the file.
3. The ingestion worker pulls the file, computes a SHA-256 content hash for idempotency, and runs the **per-page router**: native text first; gated OCR only for pages that pass the scanned-page heuristics (image-coverage ratio, empty text, GlyphlessFont prior-OCR signal); rasterize-and-vision-describe only image-bearing or vector-heavy pages, after downsampling and content-hash dedupe so identical pages are described once. PDF parsing runs in a timeout-bounded subprocess so a poison file cannot crash the worker.
4. Chunks are embedded and upserted into the tenant's Weaviate shard with a deterministic UUIDv5 so re-ingest updates rather than duplicates. Per-document status (queued, processing, done, failed) is written to Postgres for the dashboard.
5. A poison file that exhausts retries lands in a DLQ and is surfaced as `failed` with a reason, never silently dropped.

**Query/answer path:**
1. The widget POSTs the visitor's question to the API with the tenant's public widget key. The API is a Backend-for-Frontend: the model API key never reaches the browser.
2. The API screens the input for prompt injection (see guardrail, section 4), then runs the PydanticAI agent with typed deps carrying the tenant's Weaviate handle.
3. The agent's retrieve tool runs a hybrid search inside that tenant only. Tenant isolation is enforced by the shard boundary and by RLS in the relational layer.
4. The agent drafts an answer, the faithfulness guardrail grades it against retrieved chunks, and the typed output returns either a grounded answer with sources or an honest refusal verdict. The whole run is one Logfire trace; errors go to Sentry.
5. The response streams back to the widget via fetch-based streaming (not native EventSource, which cannot send an auth header cross-origin, https://developer.mozilla.org/en-US/docs/Web/API/EventSource/withCredentials).

**Eval path:**
- Offline CI gate: a golden set of question/expected-answer/expected-source rows, scored by DeepEval (faithfulness, answer relevancy, contextual precision/recall) plus one agentic metric (Tool Correctness or Task Completion). The faithfulness-style pass/fail decision uses DeepEval's deterministic DAG metric so the gate does not flap (section 4). `deepeval test run` fails the build below threshold. Cross-family judge (GPT judges a Claude-answered system).
- Online: a referenceless faithfulness scorer runs on sampled demo traces in Logfire, scores attached to the trace. Same metric family as the gate.

**Widget serving:**
- A single self-contained Vite library-mode bundle (Lit bundled in), served from a CDN with a fingerprinted filename, immutable cache, and `Access-Control-Allow-Origin: *`. The owner pastes one async script tag. `customElements.define` is guarded against double-define. The shadow root uses `:host { all: initial }` to stop host-page font/color/line-height from leaking in.

**MCP server:**
- A remote Streamable-HTTP MCP server on the Python service, single `/mcp` endpoint, Origin-validated, bearer-token-verified (Supabase JWT with issuer/audience checked), exposing the answer-plus-verdict tool. Full OAuth hardening is documented and one check is demonstrated.

---

## 3. RISK REGISTER

Top blockers from the research, each with likelihood, impact, mitigation, and spike-early flag. Cited.

| # | Risk | Likelihood | Impact | Mitigation | Spike early? |
|---|---|---|---|---|---|
| 1 | **MCP OAuth eats the whole timeline.** The 2025-11-25 spec stacks five RFCs; a real team spent ~2 weeks just understanding it and abandoned their from-scratch build (https://upstash.com/blog/mcp-oauth-implementation, https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization). | High | Critical (could sink the flagship) | Re-scope per decision 1.3: ship remote MCP with Origin validation and verified bearer token, document the full OAuth design, demonstrate audience/issuer validation only. Do NOT build the authorization server. | YES, day 1 spike to confirm the scoped version works end to end. |
| 2 | **Poison PDF crashes the ingestion worker.** Malformed PDFs segfault the MuPDF C library, which is a process crash, not a catchable Python exception (https://github.com/pymupdf/PyMuPDF/issues/4533, https://github.com/pymupdf/PyMuPDF/issues/512). | Medium | High (one bad file kills a batch) | Parse PDFs in a timeout-bounded subprocess; detect encrypted (`needs_pass`) and malformed files explicitly; route failures to DLQ with a reason. | YES, the OCR/vision spike (day 3) must include the crash-isolation harness. |
| 3 | **Vision/OCR cost and latency blow up.** OCR is ~1000x slower than native extraction (https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html); vision cost is dimension-driven with a hard 2000px rule above 20 images per request (https://platform.claude.com/docs/en/build-with-claude/vision). | High | Medium | Gate OCR behind scanned-page heuristics; describe only image-bearing/vector pages; downsample to <=2000px; content-hash-dedupe pages before any paid call (https://milvus.io/ai-quick-reference/what-caching-strategies-are-effective-for-multimodal-rag). | YES, in the day 3 spike. |
| 4 | **LLM-as-judge CI gate flaps red/green.** Temperature 0 does not guarantee determinism (batching, MoE routing); judges have measured self-inconsistency (https://arxiv.org/abs/2510.27106); G-Eval is explicitly non-deterministic (https://deepeval.com/docs/metrics-llm-evals). A flaky gate destroys the red-to-green story. | High | High (the gate is a headline artifact) | Use DeepEval's deterministic DAG metric for the gate decision (https://deepeval.com/docs/metrics-dag); pin model version; set thresholds with margin; for any non-DAG judge, average 3 runs and majority-vote. The headline red-to-green demo uses the DAG metric so it is reproducible. | Design day 1; build day 7-8. |
| 5 | **Prompt injection on a public widget.** The widget is internet-facing; OWASP LLM01 says RAG and fine-tuning do not fully mitigate injection, and indirect injection via retrieved docs is a live surface (https://genai.owasp.org/llmrisk/llm01-prompt-injection/, https://www.lakera.ai/blog/indirect-prompt-injection). | High | High (it is the demo's credibility) | Defense in depth: a lightweight pre-screen model (Claude Haiku harmlessness screen, https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks); spotlighting/delimiting of retrieved content; system prompt forbids executing instructions found in retrieved docs; output faithfulness guardrail. Demonstrate with an adversarial test set and a block rate, not one screenshot (https://www.promptfoo.dev/docs/red-team/owasp-llm-top-10/). | Design day 1; build days 6 and 9. |
| 6 | **Postgres RLS looks enforced but is not.** Table owners and superusers bypass RLS by default; you must run as a non-owner role or `FORCE ROW LEVEL SECURITY`; missing `WITH CHECK` leaves writes open; `user_metadata`-based policies are an escalation vector (https://www.postgresql.org/docs/current/ddl-rowsecurity.html, https://supabase.com/docs/guides/database/postgres/row-level-security). | Medium | Critical (silent cross-tenant leak) | Run the app as a dedicated non-owner, non-BYPASSRLS role; `FORCE` RLS; add `WITH CHECK` on every write policy; base policies on `app_metadata`; index `tenant_id`; wrap `auth.*()` in a subselect. Prove with a test that tenant A cannot read or write tenant B. | YES, day 2 (the isolation test is the day-2 artifact). |
| 7 | **Widget breaks or is broken by the host page.** Inherited CSS pierces the shadow boundary; z-index is a host-stacking-context problem with "no clean solution"; double-define throws and breaks the page; host CSP can block the script and inline styles (https://lit.dev/docs/components/styles/, https://dev.to/issuecapture/shadow-dom-css-isolation-how-to-embed-a-widget-without-breaking-the-host-page-4oio, https://developer.mozilla.org/en-US/docs/Web/API/CustomElementRegistry/define, https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP). | Medium | Medium | `:host { all: initial }`; guard `customElements.define`; attach to `document.body` with `position: fixed`; inject CSS as a string (not `<link>`); test on three very different host pages; document the CSP allowlist requirement. | Day 10-11 (widget days). |
| 8 | **Cross-origin streaming fails.** Native EventSource cannot send an Authorization header; credentialed CORS forbids wildcard origin (https://developer.mozilla.org/en-US/docs/Web/API/EventSource/withCredentials, https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS). | Medium | Medium | Use fetch-based streaming with a Bearer header; reflect the validated Origin (not wildcard) when credentials are needed; handle the OPTIONS preflight. Decide this on the first widget day. | Day 10. |
| 9 | **Model API key leaks via the client bundle.** Any secret in browser JS is shared with every attacker (https://blog.gitguardian.com/stop-leaking-api-keys-the-backend-for-frontend-bff-pattern-explained/). | Low | Critical | Backend-for-Frontend: the widget calls our API, our API calls the model. The bundle holds only the public widget key. Secrets in env/secret manager. | Baked in from day 1. |
| 10 | **Cold start blows the latency budget.** Python cold starts are dominated by heavy imports (NumPy/torch can be >90% of cold-start latency, https://arxiv.org/pdf/2512.16066). Target p95: TTFT under 500ms, total under 3s for an interactive widget (https://www.boundev.ai/blog/llm-inference-latency-time-to-first-token). | Medium | Medium | Keep heavy ML imports off the request path (ingestion worker only); run the API on a warm container, not cold serverless; stream tokens so perceived latency is low; prompt-cache the static system prompt (cache reads $0.30/M vs $3.00/M, https://www.anthropic.com/news/prompt-caching). | Day 8-9. |

The four worst (1, 2, 4, 5) are all spiked in the first half of the plan. That is deliberate: surface the blockers while there is still time to re-scope around them.

---

## 4. THE TWO-WEEK PLAN

Ten to twelve working days. Riskiest spikes first. Each day ends in a real artifact. The live hosted demo is a tracked milestone (day 9, hardened day 12). Standards baked in from day 1: clean repo, tests beside the code, minimal comments (why not what), typed Python, the eval gate wired before the agent is called done.

**Day 1 — Foundations plus the MCP spike (riskiest thing first).**
Repo, tooling, CI skeleton, typed FastAPI surface, Backend-for-Frontend secret handling, Supabase auth issuing JWTs. Then the day-1 spike: stand up a remote Streamable-HTTP MCP server with Origin validation and a verified bearer token, confirm an MCP client can list and call a stub tool. This proves the scoped MCP plan (decision 1.3) works before anything depends on it.
Artifact: an MCP client calls an Origin-validated, token-checked remote tool; CI runs.

**Day 2 — Tenant isolation, proven.**
Postgres schema for tenants, users, documents, configs. RLS on every tenant table, FORCED, app-role is non-owner and non-BYPASSRLS, `WITH CHECK` on writes, `app_metadata`-based policies, `tenant_id` indexed. Weaviate collection with multi-tenancy enabled, two tenants, deterministic UUIDv5 upsert helper.
Artifact: a test proves tenant A cannot read OR write tenant B, in both Postgres and Weaviate. This is the multi-tenancy signal, finished.

**Day 3 — The OCR/vision spike (second-riskiest thing).**
The per-page router: native text, gated OCR behind scanned-page heuristics, rasterize-and-vision for image/vector pages, downsample, content-hash dedupe. PDF parsing in a timeout-bounded subprocess. Encrypted and malformed detection.
Artifact: a scanned PDF becomes searchable text; a diagram-only page is retrievable by its described content; a poison PDF lands in the DLQ with a reason instead of crashing the worker.

**Day 4 — Ingestion pipeline end to end.**
Presigned-PUT upload, queue, idempotent upsert by content hash, per-document status rows, DLQ consumer that records failure reasons. Backpressure on downstream 429.
Artifact: a duplicate upload is a no-op; 20 concurrent uploads process; one poison file shows `failed` with a reason.

**Day 5 — The agent and grounded answer.**
PydanticAI agent, typed deps carrying the tenant Weaviate handle, `@agent.tool retrieve` doing tenant-scoped hybrid search, multi-provider model behind one interface with a fallback. Typed honesty-verdict output.
Artifact: the agent answers a grounded question end to end with sources, inside one tenant only.

**Day 6 — Refusal plus the injection guardrail (part 1).**
Faithfulness guardrail as a typed verdict: refuse honestly when ungrounded. Prompt-injection pre-screen (lightweight harmlessness model) plus spotlighting/delimiting of retrieved content plus a system prompt that forbids executing retrieved instructions.
Artifact: an off-corpus question gets an honest refusal; a "ignore previous instructions" attempt is blocked, not obeyed.

**Day 7 — Observability plus the eval gate, designed to not flap.**
Logfire instrumentation (one trace per run), Sentry on the backend. DeepEval golden set. The CI gate decision built on the deterministic DAG metric so it is reproducible; thresholds set with margin.
Artifact: a run shows a full span tree; a regression below threshold fails the build, reproducibly.

**Day 8 — Red-to-green plus agentic eval plus online scorer.**
Push a deliberately bad change: CI goes red (reproducibly, because the gate is DAG-based). Fix: green. Add one agentic metric (Tool Correctness or Task Completion). Add the referenceless faithfulness scorer on sampled traces in Logfire. Prompt-cache the static system prompt; cap `max_tokens`.
Artifact: the real red GitHub Actions run then the green one; live faithfulness scores on traces.

**Day 9 — Dashboard plus the live hosted demo goes up (MILESTONE).**
React plus Vite dashboard: upload, watch status, see failure reasons, see eval results, view a trace link. Deploy the API, the agent, Weaviate, and Postgres to a hosted environment. Seed two demo tenants with real public content (developer docs is the recommended corpus, per the prior plan's domain decision).
Artifact: a hosted URL where the dashboard is live and seeded. The system is reachable on the internet.

**Day 10 — The embeddable widget.**
Lit plus Shadow DOM widget, `:host { all: initial }`, inline SVG icons, fetch-based streaming with a Bearer header, guarded `customElements.define`. Vite library-mode single bundle, served from a CDN with immutable cache and CORS. Isolated Sentry BrowserClient.
Artifact: the script-tag embed works cross-origin on three very different host pages without breaking them, and streams answers.

**Day 11 — The injection demo plus widget telemetry plus polish.**
The recruiter-facing money shot: on the live demo, a visitor asks something off-corpus and the widget refuses with an honesty verdict; a visitor tries a prompt injection and it is blocked. Run an adversarial test set and record a block rate. Per-tenant usage telemetry. Tighten the demo flow so a recruiter can click one link and watch it refuse a hallucination and resist an injection in under a minute.
Artifact: the live demo performs the refuse-and-resist sequence on demand; a documented injection block rate.

**Day 12 — Hardening, README, and the demo clip.**
Latency check against the p95 budget, secrets audit, Logfire sampling, the MCP OAuth hardening write-up and the one demonstrated audience/issuer check, the scale-seam write-up (Weaviate ceilings, the Cloudflare Queues swap, the RLS footguns avoided), architecture diagram, README essay with the week's real numbers, and a 60-to-90-second demo clip.
Artifact: a documented, traced, evaluated, injection-resistant, two-tenant system with a live hosted demo and a demo clip. Finished.

**If a day slips:** day 11's telemetry is the buffer (the injection demo is not). The non-negotiables are the day-2 isolation test, the day-3 poison-PDF survival, the day-8 reproducible red-to-green, and the day-9 live hosted demo. Those four are the spine; protect them.

---

## 5. EXPLICIT OPEN DECISIONS FOR THE OWNER

Each with a recommendation and rationale.

1. **Multi-tenant scope.** Recommendation: single-tenant-excellent with two tenants and a proven isolation seam (decision 1.1). Rationale: you get the full senior signal from two tenants plus a passing isolation test plus a cited scale write-up, and you avoid the operational traps (shard ceilings, tenant-state bugs, backup gaps) that would eat days without buying interview value. If a specific target employer is explicitly a multi-tenant-vector-DB shop, you can seed more tenants, but do not operate the tiering.

2. **MCP OAuth depth.** Recommendation: scoped MCP (remote, Origin-validated, token-verified) plus a written OAuth hardening plan plus one demonstrated check (decision 1.3). Rationale: the research shows full MCP OAuth is a multi-week effort that a real team abandoned; the scoped version still demonstrates the senior signal and finishes on time. Only build the full authorization server if you drop something else of equal size, which I do not recommend.

3. **Edge/app split.** Recommendation: one Python service plus CDN widget, Cloudflare optional and additive (decision 1.2). Rationale: two perfect deploy targets in two weeks is a finishing risk; one well-built service with a documented scale-out path is more finishable and equally defensible. If you specifically want Cloudflare on your resume, add the Worker as a thin front in day 12's buffer, not on the critical path.

4. **Domain/seed corpus.** Recommendation: developer docs (carried from the prior plan's Option A), because it makes hybrid retrieval visibly necessary (error codes and API symbols are where dense-only retrieval fails) and the audience reviewing the GitHub is developers. Switch the seed to a regulated corpus only if a specific fintech/legal/health employer is the target; the architecture does not change.

5. **Online eval surface.** Recommendation: Logfire live-evals, one surface (decision 1.4). Rationale: the traces already live there; a second eval surface is complexity without payoff in a demo. The closed-loop production story is described in the README as the next step.

6. **Judge pairing.** Recommendation: generate with Claude, judge with GPT (or Gemini), and build the gate decision on DeepEval's DAG metric. Rationale: cross-family judging mitigates self-enhancement bias, and the DAG metric makes the gate reproducible so the red-to-green story is reliable (https://deepeval.com/docs/metrics-dag).

7. **Vision direct-PDF vs self-render.** Recommendation: self-render and describe only image-bearing pages, dedupe by content hash. Rationale: it controls cost, parallelizes, and avoids the 32MB/100-page direct-PDF caps (https://platform.claude.com/docs/en/build-with-claude/pdf-support).

---

*Where this plan overrides v2: multi-tenancy is built for two tenants and proven by a test rather than operated at scale; the edge/app split collapses to one Python service plus a CDN; MCP OAuth is scoped to a real remote server plus a written hardening plan rather than a full authorization server; online eval is a working scorer on sampled demo traces rather than a full production sampling pipeline. The vision/OCR path, the isolation design, the eval rigor, the guardrail, and the tool choices are kept from v2 and hardened with cited, real-world failure modes. Every override serves one goal: a flagship that is genuinely finished, polished, and recruiter-clickable in two weeks, which reads stronger than an ambitious system left half-built.*

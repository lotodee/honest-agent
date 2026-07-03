# ARCHITECTURE.md: honest-agent, the architecture blueprint

**Status:** DRAFT, awaiting owner review. Produced 2026-07-02 by Fable 5 under the mandate in `FABLE5_BRIEF_AND_MANDATE.md`. Phase 3 (the full day-by-day plan) does not start until this is approved.
**Relationship to the locked spec:** `Planning/BUILD_SPEC_LOCKED.md` remains the source of truth. This document does three things: (1) it corrects factual claims in our plans that fresh research refuted, each proposed as a written spec delta for the owner to accept or reject; (2) it gives the full system and code architecture, with concrete code; (3) it reconciles the architecture with the code that already exists after Day 1.
**Honesty note:** everything below is labeled BUILT (exists in the repo today, verified by a code survey on 2026-07-02) or PLANNED (does not exist yet). Nothing planned is described as done. All research citations were fetched on 2026-07-02 unless a publication date is shown.

---

## 0. How to read this document

Section 1 is the part the owner must act on: research findings that contradict our written plans, each with a proposed correction. Section 2 is the system architecture (components, trust boundaries, data flows, deployment). Section 3 is the code architecture, the primary deliverable: the folder tree, the layering rules, and concrete code for every seam. Section 4 gathers the security design in one place. Section 5 proposes targeted improvements to CLAUDE.md and the review skills, only where they serve the architecture. Section 6 reconciles with the existing Day-1 code. Section 7 sketches what this means for Days 2 to 12 (the full plan comes after approval).

A recurring idea used throughout: a **seam** is a deliberate boundary in the code where one side can be replaced without touching the other. The three-door auth model, the retrieval port, and the model provider are all seams. Good seams are what make a 12-day build survivable: when research or a provider changes (and Section 1 shows how much changed in four days of model-provider news), only the adapter behind the seam moves.

---

## 1. Research corrections and proposed spec deltas (owner decision required)

Everything in this section is backed by primary sources fetched 2026-07-02. Each item states what our documents currently claim, what is actually true, and the exact correction proposed. None of these breaks a Section 4 hard constraint; several make the constraints easier to honor. Where a correction touches `BUILD_SPEC_LOCKED.md`, accepting it means editing that file (and its mirror claims in CLAUDE.md and the skills), because the spec must never carry a claim we know is false.

### Delta 1 (most important): the DAG metric is NOT "rule-based, no paid judge"

**What we claim:** the locked spec says the CI gate uses "DeepEval's deterministic DAG metric (rule-based, no paid judge, does not flap)."
**What is true:** DeepEval's own documentation tags `DAGMetric` as an LLM-as-a-judge metric. Every judgement node in the graph (`TaskNode`, `BinaryJudgementNode`, `NonBinaryJudgementNode`) executes an LLM call; only the mapping from verdicts to scores is deterministic. Worse for the "no paid judge" claim, the metric's `model` parameter defaults to a paid OpenAI model (`gpt-5.4` in DeepEval 4.0.x) unless we explicitly pass a Gemini judge. Sources: https://deepeval.com/docs/metrics-dag (fetched 2026-07-02); the metric's design post, https://www.confident-ai.com/blog/how-i-built-deterministic-llm-evaluation-metrics-for-deepeval (published 2025-02-09, updated 2025-08-08), which calls it "deterministic, structured around LLM-powered decision trees."
**Why this still mostly works for us:** the DAG approach is genuinely the lowest-variance judged metric available. Constrained binary verdicts flip far less often than a continuous G-Eval score, and the design post shows it works well with weaker, cheaper models, which suits a Gemini Flash-tier judge. But "does not flap" is engineering, not a property we get for free: temperature 0 does not guarantee determinism (batch non-invariance in inference servers, documented at https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/, 2025-09-10), and Vertex's `seed` parameter is documented as "best effort" (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/GenerationConfig).
**Proposed correction (a three-lane gate, which is stronger than the original claim):**
- Lane 1, hard-deterministic and blocking: plain pytest assertions on the typed output (schema shape, citation presence, refusal-on-empty-context behavior) plus DeepEval's `ToolCorrectnessMetric`, whose core score is pure set matching of tools called against tools expected, with no LLM at all, provided we do NOT pass `available_tools` (verified at https://deepeval.com/docs/metrics-tool-correctness). This lane can never flap and is the reproducible core of the red-to-green story.
- Lane 2, DAG-judged and blocking with margin: the DAG faithfulness gate, judge explicitly pinned to a Gemini model (set both via `deepeval set-gemini` and per-metric `model=`, because the default is paid OpenAI), temperature 0 plus seed, DeepEval result caching in CI keyed on golden-set hash so unchanged cases cost zero tokens, threshold set with a measured margin (run the golden set several times once, measure the spread, set the gate 2 to 3 spreads below the observed baseline), and `-r` repeats for borderline cases.
- Lane 3, warn-only: G-Eval or Task Completion style judged metrics, reported but never blocking.
The red-to-green demo drives a Lane 1 failure (or a Lane 2 failure far beyond the margin), so the headline artifact is reproducible by construction.
**Spec edit if accepted:** replace "deterministic DAG metric (rule-based, no paid judge, does not flap)" with "a three-lane gate: deterministic assertions plus Tool Correctness (no LLM) as the reproducible core, a DAG faithfulness metric with a Gemini judge and a measured threshold margin as the judged lane, and warn-only judged metrics." This is more honest and reads more senior, because it names the variance and engineers around it instead of denying it.

### Delta 2: PydanticAI is now V2, and several idioms in our documents are removed

**What we claim:** CLAUDE.md says "Agent `instrument=True`"; the plans assume V1-era wiring.
**What is true:** PydanticAI v2.0.0 went stable 2026-06-23 (current 2.x as of 2026-07-02). `Agent(instrument=True)` is removed; instrumentation is now `logfire.instrument_pydantic_ai()` globally or an `Instrumentation` capability per agent. Vertex access is `GoogleModel` with `GoogleCloudProvider` (model string prefix `google-cloud:`), built on the `google-genai` SDK; the old `vertexai` extra is gone. Bare model names without a prefix now raise an error. Union `output_type` needs a `# type: ignore` under mypy strict until PEP 747 lands, and the docs recommend against fighting it. Sources: https://pydantic.dev/docs/ai/project/changelog/ ; https://pydantic.dev/docs/ai/models/google/ ; https://pydantic.dev/docs/ai/core-concepts/output/ (all fetched 2026-07-02).
**Proposed correction:** pin `pydantic-ai>=2,<3`. Use `logfire.instrument_pydantic_ai()` once at startup. Use `GoogleCloudProvider` with service-account credentials. For the honesty verdict, do NOT use a top-level union as `output_type`; use a single wrapper model with a discriminated-union field (Section 3.6 shows the code), which sidesteps the type-checker problem entirely and keeps mypy strict clean. Update CLAUDE.md's one stale line.

### Delta 3: pin the MCP SDK and name the spec revision, because the protocol changes on 2026-07-28

**What we claim:** remote Streamable-HTTP MCP server, current spec, full OAuth documented.
**What is true:** the ratified spec revision today is 2025-11-25. A 2026-07-28 revision was locked as a release candidate on 2026-05-21 and goes final in 26 days: it removes the `initialize` handshake and protocol sessions entirely (stateless core), adds `server/discover`, and the Python SDK v2 beta renames `FastMCP` to `MCPServer`. Existing servers keep working (new clients fall back to `initialize`). The 2025-11-25 revision also made "servers MUST return HTTP 403 for invalid Origin" literal spec text, which is exactly what our Day-1 middleware does. Sources: https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/ (2026-05-21); https://blog.modelcontextprotocol.io/posts/sdk-betas-2026-07-28/ (2026-06-29); https://modelcontextprotocol.io/specification/2025-11-25/changelog .
**Proposed correction:** pin `mcp>=1.27,<2` in pyproject. State in the README and MCP write-up: "implements MCP 2025-11-25; designed stateless (`stateless_http=True`), which is exactly the direction the 2026-07-28 revision takes the protocol." This turns a churn risk into a forward-compatibility talking point, and it costs nothing because our server is already stateless. Our Origin-403 behavior should cite the spec changelog.

### Delta 4: Gemini model and embedding names in our documents are stale

**What we claim (implicitly, in older planning docs):** Gemini 2.x-era model names.
**What is true:** the Vertex catalog as of 2026-07-02 lists the Gemini 3 line (3.1 Pro, 3 Pro, 3 Flash, 3.1 Flash-Lite) with 2.5 still available; the 2.5 line passed a scheduled deprecation for some pinned versions on 2026-06-17. For embeddings, `gemini-embedding-001` is the stable default and Gemini Embedding 2 is the new flagship; `text-embedding-005` reads legacy. Free credits are the $300, 90-day trial credit, with Dynamic Shared Quota (no guaranteed throughput). Implicit prompt caching is on by default for Gemini 2.5+ and 3 models at a 90 percent discount on cached input tokens; batch mode is a 50 percent discount and is the right lane for ingestion-time vision calls; Gemini 3 adds a per-part `media_resolution` control (about 70 tokens per image at low, 258 at standard) for cheap image classification. Sources: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models ; https://ai.google.dev/gemini-api/docs/models (updated 2026-06-30); https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-context-caching ; https://ai.google.dev/gemini-api/docs/media-resolution (all fetched 2026-07-02).
**Proposed correction:** name models in ONE place (`core/settings.py`) and nowhere else. Recommended defaults, verified current: `google-cloud:gemini-3-flash` for generation and vision description, a Flash-Lite-tier model for the injection pre-screen and page classification, `gemini-embedding-001` for embeddings. Structure vision prompts with the static instructions first and the image last, to farm implicit cache hits. Because model names now demonstrably rot within months, the 90-day-credit clock and the model-name pin belong in the README's honesty section.

### Delta 5: object storage should be Supabase Storage, not R2 (close an open decision)

**What we claim:** "R2 or Supabase Storage," undecided.
**What is true:** R2 presigned PUT cannot enforce a maximum object size at all (no `content-length-range` equivalent; confirmed at https://developers.cloudflare.com/r2/api/s3/presigned-urls/ , page updated 2026-04-24, and https://github.com/cloudflare/cloudflare-docs/issues/19190 ). Supabase Storage enforces both `file_size_limit` and `allowed_mime_types` server-side at upload time, per bucket (https://supabase.com/docs/guides/storage/uploads/file-limits). We already run Supabase for auth and Postgres, so it is one fewer account, one fewer credential, and the free plan's 50 MB per-file cap is comfortably above our 25 MB target cap.
**Proposed correction:** lock Supabase Storage with a `tenant-docs` bucket, `file_size_limit` 25 MB, `allowed_mime_types` restricted to PDF, and tenant-prefixed object keys generated server-side. R2 remains the documented alternative if egress cost ever matters.
**Companion clarification (closes a scope hole a self-review caught):** the PDF-only bucket covers the UPLOAD lane only. The spec's product line also includes "a small site crawl," and the Day-9 seed corpus is developer docs (HTML/markdown), neither of which is a PDF. So ingestion has two source lanes sharing one pipeline tail: lane 1, uploaded PDFs, via the presigned bucket; lane 2, crawled or seeded pages, fetched by the WORKER itself (never by the API on the request path) from an owner-supplied URL list capped at a small page count, with an SSRF guard (the fetcher resolves and refuses private, loopback, and link-local addresses, and follows redirects only within the allowlisted host). Both lanes converge at the chunking step. The seed script (`scripts/seed_local.py`, BUILT as a stub) uses lane 2 directly. If the owner prefers to cut the crawl entirely for the 12 days, that is a one-line spec delta to write down instead; the architecture supports either call.

### Delta 6: the database connection profile must be decided as ONE decision

**What nobody wrote down yet:** Supabase offers a direct connection (port 5432) and a transaction-mode pooler (Supavisor, port 6543). Our tenant-scoping design (Section 3.4) sets a per-transaction session variable that RLS policies read. Under transaction-mode pooling this is only safe if the `set_config` call and the queries share one transaction, asyncpg additionally needs `statement_cache_size=0` there, and LISTEN/NOTIFY does not work at all. On a single always-on container, none of that pain buys anything. Sources: https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL ; https://www.pgbouncer.org/features.html ; https://www.postgresql.org/docs/current/functions-admin.html (all fetched 2026-07-02).
**Proposed correction:** one service, one small asyncpg pool (5 to 10 connections) straight to the direct port. Prepared statements, `set_config`, and NOTIFY all just work. Document the pooler rules (transaction-scoped set_config, no prepared statements, no NOTIFY) as the "when we scale to many instances" note. This is the kind of one-line decision that silently corrupts tenancy if left implicit.
**Build-time verification required:** Supabase's direct connection has historically been IPv6-only on the free plan, and some free hosts lack IPv6 egress. If the chosen host cannot reach port 5432, the fallback is Supavisor SESSION mode (not transaction mode), which preserves session semantics including `set_config` and prepared statements. Verify reachability during the Day-2 setup, not on deploy day.

### Delta 7: Weaviate operational invariants (small but load-bearing)

Three verified facts to encode as code, not prose. First, do NOT enable `auto_tenant_creation`: it silently creates a new tenant shard on any typo in a tenant name, and it has an open multi-node activation bug (https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy ; https://github.com/weaviate/weaviate/issues/8651). With exactly two known tenants, create both explicitly at bootstrap and let an unknown tenant hard-fail. Second, Weaviate backups silently exclude tenants that are not ACTIVE (same docs page, backups section); any backup step must assert both tenants are ACTIVE first. Third, our CI's Weaviate 1.38.x is the current minor (v1.38.0 announced 2026-06-09), and the v4 Python client's current idioms are `collections.use(...)`, `with_tenant(...)`, and `Configure.Vectors.self_provided()` (the older `Vectorizer.none` and `NamedVectors` spellings were replaced in client 4.16). Sources: https://forum.weaviate.io/t/weaviate-v1-38-0-release-announcement/22525 ; https://docs.weaviate.io/weaviate/manage-collections/vector-config (fetched 2026-07-02).

### Delta 8 (flagged risk, decision can wait until Day 8, spike sooner): where does Weaviate LIVE in the deployed demo?

The spec locks free-tier, card-free hosting on Render or Fly, and Weaviate self-hosted via Docker. Locally that is trivial. Deployed, it is the one part of the Day-9 story with no verified plan: Render's free web services are small single containers with no sidecars (512 MB RAM at last check; verify current limits at build time, they are not cited here because free-tier terms change quietly), and running Weaviate next to the API inside that envelope is untested by us. Options, in recommended order: (a) run Weaviate and the API in ONE container (a supervisor process starting both), accepting the memory squeeze for a two-tenant demo corpus, (b) Fly.io with a small always-on machine and a volume, if its current free allowances still permit (must be verified against Fly's pricing page at build time, and the spec requires card-free, which Fly may not satisfy), (c) Weaviate Cloud's 14-day sandbox created no earlier than Day 8, accepting the expiry clock and documenting it. I am not inventing a verdict here: this needs a one-hour spike, and I recommend doing that spike on Day 4 rather than discovering it on Day 9. This is a finishability risk in the current plan that no existing document names.

### Delta 9: let PydanticAI's Model abstraction BE the multi-provider seam

**What the spec locks:** "the multi-provider abstraction is still built (engineering signal + a real fallback seam), but Gemini is the only live model." The Day-1 code carries a hand-rolled `ModelProvider` Protocol in `agent/model.py` toward that clause.
**What I propose, in writing because this touches a locked sentence:** satisfy the clause with PydanticAI's own `Model` abstraction instead of a second hand-rolled layer. PydanticAI models are already swappable objects (`GoogleModel`, `FallbackModel`, `TestModel`); `FallbackModel(primary, secondary)` is a real, documented fallback seam (https://pydantic.dev/docs/ai/models/overview/), and the architecture confines model construction to one function (`build_model`, Section 3.6) driven by settings. Wrapping a port around a port adds a layer that does nothing, and deleting the unused hand-rolled Protocol follows rule 3 of Section 3.1. The engineering signal the clause wants (a provider swap is a config change, a fallback chain is one constructor) is preserved and demonstrable in tests with `TestModel`. If the owner prefers the literal hand-rolled interface anyway, the cost is small and the architecture accommodates it; but the recommendation is to let the framework's seam count.

### What did NOT change

Verified and standing: the three-door auth model matches current security guidance, and MCP Origin-403 is now literal spec text. Postgres RLS practice (FORCE, non-owner role, WITH CHECK, the subselect optimization, `tenant_id` indexes) is confirmed current, with Supabase's advisor lints as the authority (https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv). PyMuPDF stays the right PDF pick for an open-source project (AGPL is satisfied by the public repo; the segfault-in-subprocess defense is confirmed by open issues #1507, #2907, #556); pypdfium2 is the documented license-safe alternative. The widget stack (Lit 3.3, `:host { all: initial }`, guarded define, body-mounted fixed positioning, Vite library mode single file, fetch streaming, isolated Sentry BrowserClient) is fully current. OWASP LLM01 still says RAG does not mitigate injection, and Microsoft's spotlighting paper (https://arxiv.org/abs/2403.14720, 2024-03-20) reports datamarking cutting indirect-injection success from over 50 percent to under 2 percent in their tests, which makes it our cheapest high-impact control.

---

## 2. System architecture

### 2.1 Components and trust boundaries

One Python service is the application. Everything else is either a data store, a static asset, or an external caller.

```
                        TRUST DOMAIN: PUBLIC INTERNET (untrusted)
  ┌────────────────┐   ┌──────────────────┐   ┌───────────────────────┐
  │ Owner browser  │   │ Visitor browser  │   │ External AI caller    │
  │ (dashboard,    │   │ (host page +     │   │ (an MCP client, e.g.  │
  │ Supabase login)│   │ embedded widget) │   │ someone's agent)      │
  └───────┬────────┘   └────────┬─────────┘   └──────────┬────────────┘
          │ Supabase JWT        │ public widget key      │ external-caller token
          │ (ES256, app_        │ + Origin/Referer       │ (HS256, iss/aud bound
          │ metadata tenant)    │ + rate limit + cap     │ to THIS server)
  ════════╪════════════════════╪════════════════════════╪══════ trust boundary
          ▼                    ▼                        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ THE PYTHON SERVICE (FastAPI + PydanticAI, one deployable)       │
  │                                                                 │
  │  Door A: owner routes    Door B: visitor gate    Door C: /mcp   │
  │  (Depends-based JWT      (middleware: key,       (ASGI middle-  │
  │  verify)                 origin, size, rate,     ware: Host,    │
  │          │               sanitize)               Origin, token) │
  │          └───────────┬───────┴──────────┬───────────┘           │
  │                      ▼                  ▼                       │
  │         OwnerRequestContext  VisitorRequestContext              │
  │                      ExternalCallerContext                      │
  │                      (immutable, one type per door,             │
  │                       tenant comes ONLY from the credential)    │
  │                             │                                   │
  │                             ▼                                   │
  │   CORE CAPABILITIES (plain typed functions, no HTTP knowledge)  │
  │   answer(tenant_id, query) -> AnswerResult   (BUILT as stub)    │
  │   retrieve(tenant_id, query) -> list[Source] (BUILT as stub)    │
  │   enqueue_document(tenant_id, object_key) -> JobId  (PLANNED)   │
  │                             │                                   │
  │   guardrails (pre-screen, spotlight, verdict check)             │
  │   agent (PydanticAI, Gemini via Vertex behind a seam)           │
  │   retrieval (port -> Weaviate adapter, tenant-scoped)           │
  │   ingestion worker (lifespan task: queue, per-page router,      │
  │       PDF subprocess, DLQ)                                      │
  └───────┬──────────────┬───────────────┬───────────────┬─────────┘
          ▼              ▼               ▼               ▼
  ┌───────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐
  │ Postgres/ │  │ Weaviate     │  │ Supabase  │  │ Vertex AI    │
  │ Supabase  │  │ (multi-      │  │ Storage   │  │ (Gemini API  │
  │ (RLS      │  │ tenancy on,  │  │ (presigned│  │ only, the    │
  │ FORCED)   │  │ 2 tenants)   │  │ PUT)      │  │ only paid    │
  └───────────┘  └──────────────┘  └───────────┘  │ credential)  │
                                                  └──────────────┘
  Static: widget.js (Lit, CDN, immutable)  dashboard (React+Vite)
  Observability: Logfire (traces, one per run)  Sentry (errors only)
```

The load-bearing property, already BUILT and tested on Day 1: the three doors never collapse. Each door verifies its own credential kind, resolves the tenant from that credential only, and produces its own immutable context type. No request input (body, header, query string) can set or change a tenant. The core capabilities take a context, not a token: by the time core code runs, authentication is finished and cannot be re-litigated deeper in the stack.

### 2.2 Data flow: ingestion (PLANNED, Days 3 to 4)

1. The owner (Door A) asks the API for an upload slot. The API creates a presigned PUT URL against the tenant-prefixed key `tenants/{tenant_id}/{uuid}.pdf` in the `tenant-docs` bucket. The file never streams through the API process. Bucket policy enforces the size cap and PDF-only MIME type server-side (Delta 5).
2. The owner's browser PUTs the file to storage, then confirms. The API inserts a job row: `INSERT ... ON CONFLICT DO NOTHING` on a unique `(tenant_id, content_hash)` index, so a duplicate upload is a no-op by construction. The job row carries `tenant_id NOT NULL`, the object key, `status`, `attempts`, `visible_at`.
3. The ingestion worker (an asyncio task started in the app's lifespan, Section 3.8) claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED` (the standard Postgres queue primitive, https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE). Claiming sets a lease (`visible_at = now() + lease`), so a crashed worker's job becomes claimable again. This is a real queue with durable rows, exactly what the spec allows for the demo, and the README documents Cloudflare Queues or SQS as the scale-out swap.
4. Per-page routing inside the worker: PDF opened in a timeout-bounded SUBPROCESS (a poison PDF segfaults the C library, which kills a process, not an exception; the subprocess dies, the worker survives). Native text extraction first. OCR only for pages passing the scanned-page heuristics (near-zero extractable text plus image coverage of roughly 95 percent of the page rect, thresholds borrowed from PyMuPDF4LLM's hybrid-OCR gate, https://pymupdf.io/blog/hybrid-ocr-in-pymupdf4llm). Rasterize-and-describe with Gemini vision only for image or vector-heavy pages, at 150 to 200 DPI (Gemini tiles and downsamples images to fixed token budgets, so higher-DPI renders spend tokens on pixels the model discards; token accounting per https://ai.google.dev/gemini-api/docs/media-resolution), after a per-page content-hash dedupe so an identical page is described once and never paid for twice.
5. Chunks are embedded (`gemini-embedding-001`) and upserted into the tenant's Weaviate shard with `generate_uuid5(f"{tenant_id}:{doc_id}:{chunk_index}")`, so re-ingestion updates instead of duplicating. Per-document status rows drive the dashboard.
6. A job that exhausts `max_attempts` moves to status `dead` with `last_error` recorded: the DLQ is a queryable table state, surfaced in the dashboard as `failed` with a reason, never a silent drop. Backpressure: on a downstream 429 the worker backs off; on enqueue, a per-tenant pending-job ceiling returns 429 to the owner.

### 2.3 Data flow: visitor question (Door B; gate BUILT, core PLANNED for Days 5 to 6)

1. The widget POSTs the question with the tenant's public widget key. The in-app gate middleware (BUILT) checks, in order: body size cap BEFORE parsing, key exists, Origin/Referer exact-host match against that key's allowlist, rate limit (interface BUILT, real limiter Day 11), then sanitizes the body down to just the query string so no other field survives into the app.
2. Guardrails pre-screen the query (PLANNED, Day 6): a cheap classification call (Flash-Lite tier) plus deterministic checks; retrieved content is datamarked (Section 3.7) so documents are data, never instructions.
3. The agent (PLANNED, Day 5) runs with typed deps carrying the visitor context and the retrieval port. Its `retrieve` tool does tenant-scoped hybrid search inside the tenant's shard only.
4. The answer is graded for faithfulness against the retrieved chunks before returning. The typed result is a discriminated union: a grounded answer with sources, or an honest refusal with a verdict. The verdict is fused into the capability; there is no code path that returns an unverdicted answer.
5. The whole run is one Logfire trace; errors go to Sentry; the response streams to the widget over fetch-based streaming.

### 2.4 Data flow: MCP (Door C; BUILT as a spike with a stub core)

An external AI caller hits `/mcp` (Streamable HTTP, stateless). The ASGI middleware checks Host against a fail-closed allowlist FIRST (the DNS-rebinding defense added after the Day-1 senior review), then Origin (403 on invalid, now literal MCP spec text, changelog PR #1439), then verifies the HS256 external-caller token (signature, issuer, audience equal to this server, expiry). The verified context rides a contextvar into the tool; the inbound token is never forwarded anywhere (the spec's token-passthrough prohibition). The `answer` tool is a thin adapter over the same core capability the widget calls in-process, and the verdict is fused into its return shape.

### 2.5 Data flow: evaluation (PLANNED, Days 7 to 8)

Offline, in CI: the golden set (question, expected answer, expected sources, expected tools) lives as reviewed JSON in git. The gate runs the three lanes from Delta 1. Online: a referenceless faithfulness scorer runs on a sample of demo traces and emits standard `gen_ai.evaluation.result` events, which Logfire's live-evals surface renders natively (launched 2026-04-30, https://pydantic.dev/articles/online-evals-pydantic-logfire), so the online story is "same metric family, standard events, rendered by the tracing platform," not a custom pipeline.

### 2.6 Deployment shape

One container on Render free or Fly (Delta 8 flags the Weaviate placement risk and its spike), kept warm by a free scheduled ping under the 15-minute idle sleep. Supabase hosts Postgres, auth, and storage on its free plan. The widget bundle and dashboard are static assets on a free CDN/static host. Vertex is called as an API only. Logfire's free tier (10 million spans per month with a hard cap, per https://pydantic.dev/pricing, fetched 2026-07-02) and Sentry's free tier carry observability. The only credit card anywhere remains the Google billing card that activates the Vertex trial credit, honoring the cost posture. Logfire is configured with `distributed_tracing=False` so a malicious inbound `traceparent` header cannot poison traces (recommended for public-internet services, https://logfire.pydantic.dev/docs/how-to-guides/distributed-tracing/).

---

## 3. Code architecture (the primary deliverable)

### 3.1 The five rules that govern every file

1. **Domain-first, not file-type-first.** Each domain package owns its router, schemas, service, and adapters. This is the same layout Netflix Dispatch uses and the one the most-cited FastAPI structure guide recommends for multi-domain apps (https://github.com/zhanymkanov/fastapi-best-practices, 17k stars, actively maintained). Our repo already follows it (BUILT).
2. **Dependency direction is one-way.** `core` imports nothing from domains. Domains import `core` and may import a NEIGHBOR'S PUBLIC SEAM only (a context type, a port Protocol, a capability function), never a neighbor's internals. Concrete adapters are wired only in `main.py` and `core/deps.py` (the composition root, the one place allowed to know everything). The Day-1 code already obeys this; the survey found no violations.
3. **Selective ports, not wall-to-wall hexagonal.** A port (a `typing.Protocol` describing "I need something that can do X") exists only where a second implementation genuinely exists today: retrieval (Weaviate adapter plus an in-memory fake for tests), the rate limiter (allow-all stub today, real limiter Day 11), the widget-key store, the PDF extractor (real subprocess runner plus a fake). The LLM boundary deliberately does NOT get a hand-rolled port, because PydanticAI's `Model` abstraction with `TestModel`/`FunctionModel` and `Agent.override` IS the port, and wrapping a port in another port is ceremony. Current guidance is blunt that hexagonal-everywhere punishes small stable teams (https://dev.to/elpic/hexagonal-architecture-in-the-real-world-trade-offs-pitfalls-and-when-not-to-use-it-4a2p); the senior signal is knowing where the seams pay rent.
4. **Types are the spec.** Every cross-domain seam is a frozen dataclass, a Pydantic model, or a Protocol. mypy strict is the fast feedback loop. The one known friction point (union `output_type` under mypy strict) is solved structurally in Section 3.6, not with scattered ignores.
5. **The tenant is resolved once, at the door, and travels as data.** After the door, no code re-reads headers or tokens. Every data-touching function takes the tenant (or a context carrying it) as an explicit parameter. Weaviate access happens only through a handle already bound with `with_tenant`; Postgres access happens only inside a transaction that has already set the RLS tenant variable. There is deliberately NO way to ask "the database" a question without first saying which tenant is asking.

### 3.2 The full folder tree (target end state; markers show BUILT today vs PLANNED)

```
honest-agent/
├── .github/workflows/ci.yml          BUILT   quick-gate, integration (PG+Weaviate), eval jobs
├── backend/
│   ├── pyproject.toml                BUILT   uv, py3.12, ruff strict, mypy strict, pytest markers
│   ├── src/app/
│   │   ├── main.py                   BUILT   app factory, lifespan, router + middleware wiring
│   │   ├── core/                     BUILT   (grows: db.py gains tenant_txn; queue.py is new)
│   │   │   ├── settings.py           BUILT   one typed Settings; model names live HERE only
│   │   │   ├── errors.py             BUILT   AppError tree -> RFC 9457 problem details
│   │   │   ├── db.py                 BUILT   asyncpg pool; PLANNED: tenant_txn (3.4)
│   │   │   ├── queue.py              PLANNED SKIP LOCKED claim/complete/fail/dead (3.8)
│   │   │   ├── origins.py            BUILT   exact-host Origin/Referer/Host parsing
│   │   │   ├── bearer.py             BUILT   bearer extraction
│   │   │   ├── logging.py            BUILT   structlog JSON, contextvars binding
│   │   │   ├── observability.py      BUILT   Logfire + Sentry init (updates per Delta 2)
│   │   │   └── deps.py               BUILT   composition helpers (grows with each domain)
│   │   ├── tenants/                  BUILT   Door A + Door B live here
│   │   │   ├── contexts.py           BUILT   the three frozen context dataclasses
│   │   │   ├── schemas.py            BUILT   tenant-domain API schemas
│   │   │   ├── owner_auth.py         BUILT   ES256 JWT verify, JWKS cache, app_metadata only
│   │   │   ├── widget_keys.py        BUILT   WidgetKeyStore Protocol + Postgres impl
│   │   │   ├── gate.py               BUILT   VisitorGate middleware (size, key, origin, rate, sanitize)
│   │   │   ├── rate_limit.py         BUILT   RateLimiter Protocol (allow-all stub until Day 11)
│   │   │   ├── router.py             BUILT   owner routes
│   │   │   └── widget_router.py      BUILT   visitor routes
│   │   ├── retrieval/
│   │   │   ├── router.py             BUILT   (thin; stays thin)
│   │   │   ├── port.py               PLANNED Retriever Protocol + Chunk/Source types (3.5)
│   │   │   ├── weaviate_adapter.py   PLANNED tenant-bound hybrid search
│   │   │   ├── embedding.py          PLANNED embed texts via Vertex, with cache
│   │   │   └── service.py            BUILT-as-stub, replaced by port + adapter
│   │   ├── agent/
│   │   │   ├── router.py             BUILT   (thin; stays thin)
│   │   │   ├── schemas.py            BUILT   GroundedAnswer | HonestRefusal, Verdict, AnswerResult
│   │   │   ├── agent.py              PLANNED module-scope PydanticAI Agent (3.6)
│   │   │   ├── service.py            BUILT-as-stub -> the real `answer` capability (Day 5)
│   │   │   ├── adapters.py           BUILT   in-process + MCP thin adapters over the core fn
│   │   │   └── model.py              BUILT   seam; becomes GoogleModel construction (3.6, Delta 9)
│   │   ├── guardrails/
│   │   │   ├── prescreen.py          PLANNED injection pre-screen (cheap classifier + heuristics)
│   │   │   ├── spotlight.py          PLANNED datamarking of retrieved content (3.7)
│   │   │   ├── faithfulness.py       PLANNED the fused verdict check
│   │   │   └── router.py             BUILT-empty (seam)
│   │   ├── ingestion/
│   │   │   ├── router.py             BUILT-empty -> upload-slot + status routes
│   │   │   ├── jobs.py               PLANNED job table records + enqueue with idempotency
│   │   │   ├── worker.py             PLANNED lifespan-managed loop (3.8)
│   │   │   ├── pdf/
│   │   │   │   ├── extract.py        PLANNED runs INSIDE the subprocess (PyMuPDF)
│   │   │   │   ├── isolate.py        PLANNED subprocess runner with timeout (3.8)
│   │   │   │   └── route_pages.py    PLANNED native / OCR / vision per-page router
│   │   │   ├── chunking.py           PLANNED
│   │   │   └── storage.py            PLANNED presigned PUT against Supabase Storage
│   │   ├── eval/
│   │   │   ├── router.py             BUILT-empty (stays minimal; eval is mostly offline)
│   │   │   ├── judge.py              PLANNED the pinned Gemini judge factory
│   │   │   ├── dag_gate.py           PLANNED the DAG metric definition (Lane 2)
│   │   │   └── online.py             PLANNED sampled-trace scorer emitting gen_ai.evaluation events
│   │   └── mcp/                      BUILT   server.py (FastMCP mount, security middleware), tokens.py
│   ├── tests/
│   │   ├── unit/                     BUILT   73 unit test functions: auth, gate, tokens, origins, spine
│   │   ├── integration/              BUILT   11 tests: HTTP-level gate + mounted MCP + log hygiene
│   │   │   └── test_tenant_isolation.py  PLANNED Day 2: the dynamic RLS + Weaviate sweep (3.9)
│   │   └── eval/                     BUILT-smoke -> golden set + three-lane gate (Day 7)
│   └── scripts/
│       ├── e2e_doors.py              BUILT   re-runnable three-door proof over real HTTP
│       └── seed_local.py             BUILT-as-stub -> lane-2 seeding (Delta 5 companion)
├── supabase/                         BUILT   config; migrations/ PLANNED: schema + RLS as versioned SQL (3.4)
├── widget/                           PLANNED Lit 3 + Shadow DOM, Vite library mode (Day 10)
├── dashboard/                        PLANNED React + Vite, product-only (Day 9)
└── docs/adr/                         BUILT   architecture decision records continue per day
```

The empty routers (`ingestion`, `guardrails`, `eval`) flagged by the code survey are acceptable Day-1 seams, but each gains a one-line `501 Not Implemented` placeholder route when its day starts, never before, so the API surface never advertises capability that does not exist.

### 3.3 The shared language: contexts and results (BUILT, shown for grounding)

Every door produces its own context; the three types never merge, so a function signature always tells you which trust domain you are in:

```python
# tenants/contexts.py (BUILT)
@dataclass(frozen=True, slots=True)
class OwnerRequestContext:
    tenant_id: str
    user_id: str

@dataclass(frozen=True, slots=True)
class VisitorRequestContext:
    tenant_id: str
    widget_key: str

@dataclass(frozen=True, slots=True)
class ExternalCallerContext:
    tenant_id: str
    token_subject: str
```

And the answer capability's result carries the verdict as a required field, so honesty is a type, not a convention. This is the code as BUILT today, verbatim:

```python
# agent/schemas.py (BUILT)
class Source(BaseModel):
    document_id: str
    chunk_id: str
    score: float

class GroundedAnswer(BaseModel):
    kind: Literal["grounded"] = "grounded"
    answer: str
    sources: list[Source]

class HonestRefusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: str

# The agent's output_type. A refusal is a modeled outcome, not an exception.
Verdict = Annotated[GroundedAnswer | HonestRefusal, Field(discriminator="kind")]

class AnswerResult(BaseModel):
    answer: str          # the rendered text a client displays
    verdict: Verdict     # the structured honesty decision; never optional
```

This shape is sound and stays: `verdict` is a required field of the one result type every door returns, so no caller can receive an unverdicted answer. One PLANNED refinement when the faithfulness check lands on Day 6: today the grounded/refusal branch is the whole verdict; Day 6 adds the faithfulness GRADE (the evidence the branch decision rests on) as a `FaithfulnessGrade` model attached by the service layer, not generated by the LLM (see 3.6 for why). `HonestRefusal.reason` also tightens from `str` to an enum at that point, an intentional Day-1 simplification the survey noted.

### 3.4 Tenancy in Postgres: the tenant_txn seam (PLANNED, Day 2, the non-negotiable)

RLS (row-level security, the database refusing to show or accept rows that do not belong to the current tenant) only works if every query runs with the tenant identity set, and if the app role cannot bypass it. Both are easy to get silently wrong, so both live in exactly one place.

The migration (versioned SQL, applied by CI before integration tests):

```sql
-- supabase/migrations/0002_documents.sql (PLANNED)
CREATE TABLE documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL,
    object_key    text NOT NULL,
    content_hash  text NOT NULL,
    status        text NOT NULL DEFAULT 'queued',
    failure_reason text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, content_hash)          -- idempotent re-upload
);
CREATE INDEX documents_tenant_idx ON documents (tenant_id, created_at);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;   -- owner does not bypass

CREATE POLICY tenant_isolation ON documents
    FOR ALL TO app_user
    USING     (tenant_id = (SELECT current_setting('app.tenant_id')::uuid))
    WITH CHECK (tenant_id = (SELECT current_setting('app.tenant_id')::uuid));
```

Three deliberate choices in eight lines. FORCE, because table owners bypass RLS by default (https://www.postgresql.org/docs/current/ddl-rowsecurity.html). WITH CHECK spelled out, because a policy without it can leave cross-tenant WRITES open even when reads are sealed. The `(SELECT ...)` wrapper, because it makes the planner evaluate the setting once per query instead of once per row, Supabase's top RLS performance rule (https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv). The app connects as `app_user`: non-owner, non-superuser, no BYPASSRLS.

The single code path that sets the tenant (nothing else in the codebase may touch the pool directly for tenant data):

```python
# core/db.py (PLANNED addition)
@asynccontextmanager
async def tenant_txn(pool: asyncpg.Pool, tenant_id: str) -> AsyncIterator[asyncpg.Connection]:
    """The ONLY way to touch tenant data. Sets the RLS tenant for exactly
    one transaction; set_config(..., true) resets at commit/rollback, so a
    pooled connection can never leak tenant context to its next user."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', $1, true)", tenant_id
            )
            yield conn
```

`set_config` with the transaction-scoped flag is used instead of `SET LOCAL` because it takes a bind parameter, so the tenant id is never interpolated into SQL. An unset variable makes every policy evaluate false: fail closed. The worker uses the same wrapper (job rows carry `tenant_id`), which closes the classic "background jobs run without tenant context" leak from the failure-mode catalog.

### 3.5 Tenancy in Weaviate: the retrieval port and its adapter (PLANNED, Days 2 and 5)

The port speaks domain language and knows nothing about Weaviate:

```python
# retrieval/port.py (PLANNED)
class Retriever(Protocol):
    async def search(self, tenant_id: str, query: str, *, limit: int = 8) -> list[RetrievedChunk]: ...

@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_id: str
    chunk_index: int
    text: str
    score: float
```

The adapter binds the tenant BEFORE any query exists, using native multi-tenancy (one shard per tenant), so an unscoped query is structurally impossible, not merely forbidden:

```python
# retrieval/weaviate_adapter.py (PLANNED, v4 client current idioms)
class WeaviateRetriever:
    def __init__(self, client: weaviate.WeaviateAsyncClient, embedder: Embedder) -> None:
        self._client = client
        self._embedder = embedder

    async def search(self, tenant_id: str, query: str, *, limit: int = 8) -> list[RetrievedChunk]:
        collection = self._client.collections.use("Chunk").with_tenant(tenant_name(tenant_id))
        vector = await self._embedder.embed_query(query)
        result = await collection.query.hybrid(
            query=query,                 # keyword leg
            vector=vector,               # vector leg (self-provided: no vectorizer module)
            alpha=0.5,                   # explicit, tunable; not left to server default
            fusion_type=HybridFusion.RELATIVE_SCORE,
            limit=limit,
        )
        return [_to_chunk(obj) for obj in result.objects]
```

Bootstrap creates the collection with `Configure.multi_tenancy(enabled=True)` and `Configure.Vectors.self_provided()`, creates the two tenants EXPLICITLY, and leaves `auto_tenant_creation` off (Delta 7): a typo in a tenant name must be an error, not a fresh shard. Upserts key objects with `generate_uuid5(f"{tenant_id}:{doc_id}:{chunk_index}")`, including the tenant in the seed defensively even though shards already separate tenants. The in-memory `FakeRetriever` implementing the same Protocol is what unit tests inject.

### 3.6 The agent: PydanticAI v2, Gemini via Vertex, and the honesty output (PLANNED, Day 5)

Three current-version realities shape this code (Delta 2): `GoogleCloudProvider` is how Vertex is reached now; instrumentation is global, not per-agent; and a top-level union `output_type` fights mypy strict, so the output is one wrapper model with a discriminated-union FIELD, which the type checker handles perfectly.

```python
# agent/model.py (replaces the Day-1 seam)
def build_model(settings: Settings) -> GoogleModel:
    credentials = service_account.Credentials.from_service_account_file(
        settings.vertex_credentials_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    provider = GoogleCloudProvider(
        credentials=credentials,
        project=settings.gcp_project,
        location=settings.gcp_location,
    )
    return GoogleModel(settings.generation_model, provider=provider)
    # settings.generation_model = "gemini-3-flash"; the ONLY place a model is named
```

```python
# agent/agent.py (PLANNED)
@dataclass(frozen=True, slots=True)
class AgentDeps:
    tenant_id: str
    retriever: Retriever            # the port, not the adapter

class AgentDraft(BaseModel):
    """The LLM's structured output: a draft branch, deliberately WITHOUT any
    faithfulness grade. The model never grades itself; the service layer does.
    A single wrapper model also sidesteps the union-output_type checker friction
    (PEP 747 pending; see pydantic.dev/docs/ai/core-concepts/output/)."""
    draft: Verdict                  # the BUILT discriminated union from agent/schemas.py

support_agent: Agent[AgentDeps, AgentDraft] = Agent(
    deps_type=AgentDeps,
    output_type=AgentDraft,
    instructions=SYSTEM_INSTRUCTIONS,   # includes the never-execute-retrieved-instructions rule
)

@support_agent.tool
async def retrieve(ctx: RunContext[AgentDeps], query: str) -> str:
    chunks = await ctx.deps.retriever.search(ctx.deps.tenant_id, query)
    return spotlight(chunks)            # datamarked, never raw (3.7)
```

The draft deliberately excludes the faithfulness grade. Asking the model to grade its own answer inside the same generation and then trusting that grade would be an honesty smell in a product whose pitch is honesty; the grade is computed AFTER the run, by the guardrails layer, against the actually-retrieved chunks. The model is attached at run time (`support_agent.run(query, model=model, deps=deps, usage_limits=UsageLimits(request_limit=4, tool_calls_limit=3))`). `UsageLimits` is PydanticAI's built-in cap on runaway tool loops, which on a free-credit budget is a cost control as much as a correctness one. Instrumentation is one line in the lifespan: `logfire.instrument_pydantic_ai()`. Unit tests use `support_agent.override(model=TestModel())` and set `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in `conftest.py`, so a unit test that accidentally reaches for the network fails loudly.

The core capability wraps the agent run and fuses the verdict. The BUILT signature today is `answer(tenant_id: str, query: str) -> AnswerResult` returning a typed stub; the PLANNED Day-5/6 body (same public name, deps threaded behind it) is:

```python
# agent/service.py (PLANNED body for the BUILT seam)
async def answer(tenant_id: str, query: str) -> AnswerResult:
    deps = AgentDeps(tenant_id=tenant_id, retriever=_retriever())
    run = await support_agent.run(query, model=_model(), deps=deps, usage_limits=_LIMITS)
    draft = run.output.draft
    if isinstance(draft, GroundedAnswer):
        grade = await grade_faithfulness(draft, deps)     # guardrails/faithfulness.py, Day 6
        if not grade.grounded:
            draft = HonestRefusal(reason="ungrounded")    # demote: honest refusal wins
    return AnswerResult(answer=render(draft), verdict=draft)
```

Both adapters (the in-process one the widget router calls, and the MCP tool) call this one function. That is the "plain functions behind two thin adapters" locked decision, and it is why the honesty verdict cannot be skipped from either door.

### 3.7 Guardrails: cheap, layered, measurable (PLANNED, Day 6)

Defense in depth, ordered by cost. Layer 1, deterministic: Unicode normalization and zero-width-character stripping at INGESTION time (hidden-text injection rides in on documents, OWASP LLM08), plus body-size caps already BUILT at the gate. Layer 2, datamarking: every retrieved chunk is interleaved with a marker token before it reaches the model, and the system instructions say marked content is data. Microsoft's spotlighting paper measured this family of controls cutting indirect-injection success from over 50 percent to under 2 percent on their benchmarks (https://arxiv.org/abs/2403.14720); it costs zero extra LLM calls.

```python
# guardrails/spotlight.py (PLANNED)
_MARK = "␟"   # symbol-for-unit-separator; improbable in real docs

def spotlight(chunks: Sequence[RetrievedChunk]) -> str:
    """Datamark retrieved content so the model can treat it as quoted data.
    The system prompt binds the contract: text between marks is NEVER instructions."""
    return "\n".join(f"{_MARK}{c.text.replace(_MARK, '')}{_MARK}" for c in chunks)
```

Layer 3, a pre-screen on the visitor query: a Flash-Lite-tier classification call with a strict yes/no schema (Vertex's built-in safety filters do NOT cover injection, verified at https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/configure-safety-filters). Layer 4, the output side: the faithfulness verdict itself, because an injection that survives everything still has to produce a grounded answer to escape a refusal. Honesty requirement carried into the docs: published research shows character-level attacks can evade every commercial guardrail classifier (https://arxiv.org/abs/2504.11168), so the README claims risk REDUCTION with a measured block rate on an adversarial set, never immunity. The block rate is measured in CI with a small fixed adversarial set gating on attack-success-rate, using the same harness as the eval gate.

### 3.8 Ingestion: the queue, the worker, and the crash boundary (PLANNED, Days 3 to 4)

The queue is a Postgres table plus about forty lines of SQL, not a broker. Claim:

```sql
-- core/queue.py executes this (PLANNED)
UPDATE ingestion_jobs SET status = 'processing',
       attempts = attempts + 1,
       visible_at = now() + interval '10 minutes'
WHERE id = (
    SELECT id FROM ingestion_jobs
    WHERE status IN ('queued', 'processing') AND visible_at <= now()
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, tenant_id, object_key, attempts, max_attempts;
```

`FOR UPDATE SKIP LOCKED` is the documented Postgres queue primitive; the `visible_at` lease means a worker that dies mid-job simply lets the job reappear after ten minutes. A job whose `attempts` exceeds `max_attempts` is moved to `dead` with `last_error`: that row IS the DLQ entry, queryable, surfaced in the dashboard with its reason. We hand-roll these forty lines instead of adopting a queue library because the semantics fit in one screen, carry zero new dependencies, and are themselves a senior signal; the write-up names pgqueuer and Procrastinate as the shelf options and why they were not needed at this scale.

The worker is a lifespan-managed asyncio task in the same process (the spec's one-service constraint), with clean shutdown:

```python
# ingestion/worker.py (PLANNED)
async def run_worker(pool: asyncpg.Pool, deps: WorkerDeps, stop: asyncio.Event) -> None:
    while not stop.is_set():
        job = await claim_next_job(pool)
        if job is None:
            await _wait_or_stop(stop, seconds=2.0)
            continue
        async with tenant_txn(pool, job.tenant_id) as conn:   # same RLS wrapper as HTTP
            await process_job(conn, deps, job)

# main.py lifespan (extends the BUILT lifespan)
stop = asyncio.Event()
worker = asyncio.create_task(run_worker(pool, worker_deps, stop))
yield
stop.set()
await asyncio.wait_for(worker, timeout=30)
```

Two notes that come straight from research. First, `BackgroundTasks` is explicitly the wrong tool for this (post-response, no retry, no visibility); the durable-row worker is the accepted single-container middle ground. Second, this design is why the deploy target matters: on Cloud Run's default billing, background tasks freeze between requests (https://docs.cloud.google.com/run/docs/configuring/billing-settings), which is fine for us only because we host on an always-on free container (Render/Fly) and are NOT on Google hosting anyway per the locked constraints. The split to a separate worker process later is one new entrypoint calling the same `run_worker`, zero domain-code change.

The crash boundary: PyMuPDF's C library segfaults on malformed PDFs (documented, recurring: PyMuPDF issues #1507, #2907, #556), and a segfault kills a process, not a try/except. So extraction runs in a child process with a hard timeout:

```python
# ingestion/pdf/isolate.py (PLANNED)
async def extract_isolated(pdf_path: Path, timeout_s: float = 60.0) -> ExtractionResult:
    """Parse in a child process. A poison PDF kills the CHILD; the worker
    sees a non-zero exit or a timeout and routes the job to the DLQ with a reason."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "app.ingestion.pdf.extract", str(pdf_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        raise PoisonDocumentError(reason="extraction timeout")
    if proc.returncode != 0:
        raise PoisonDocumentError(reason=f"extractor exited {proc.returncode}")
    return ExtractionResult.model_validate_json(out)
```

Inside `extract.py`, the per-page router: native text if present; the scanned-page heuristic (near-empty text plus image bbox covering roughly 95 percent of the page) gates OCR; image or vector-heavy pages are rasterized at 150 to 200 DPI and described by Gemini vision, after a SHA-256 page-image dedupe so a repeated page is never paid for twice. Vision calls from ingestion go through Vertex batch mode where latency allows (a 50 percent cost lever, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/batch-prediction-gemini).

### 3.9 The eval harness and the isolation proof (PLANNED, Days 2 and 7)

The Day-2 isolation test is designed to be un-dodgeable. Instead of testing the tables we remember, it discovers every table carrying an RLS policy from `pg_policies` and sweeps them all; a new tenant table that forgets its policy fails CI by presence-check:

```python
# tests/integration/test_tenant_isolation.py (PLANNED, Day 2)
async def test_every_app_table_has_forced_rls(db: asyncpg.Connection) -> None:
    unprotected = await db.fetch(OPEN_TABLES_QUERY)   # app schema minus allowlist
    assert not unprotected, f"tables without FORCED RLS: {unprotected}"

@pytest.mark.parametrize("table", discovered_tenant_tables())
async def test_cross_tenant_read_and_write_blocked(pool, table: str) -> None:
    async with tenant_txn(pool, TENANT_A) as conn:
        await seed_row(conn, table, TENANT_A)
    async with tenant_txn(pool, TENANT_B) as conn:
        assert await count_rows(conn, table) == 0                    # read sealed
        with pytest.raises(asyncpg.InsufficientPrivilegeError):     # 42501
            await insert_row_for(conn, table, tenant_id=TENANT_A)   # write sealed
```

The same file proves Weaviate isolation with the two real tenants: insert into A's shard, query B's handle, assert zero hits, and assert B cannot write via A's handle. The metadata assertions (app role is non-owner, non-BYPASSRLS; `relforcerowsecurity` true) run alongside, so a quiet privilege change also fails CI.

The offline gate (Day 7) implements the three lanes from Delta 1. Goldens are reviewed JSON in git, loaded with `EvaluationDataset.add_goldens_from_json_file`, roughly 30 to 50 rows spanning how-to questions, troubleshooting, out-of-scope questions (the REFUSAL rows are where the honesty differentiator lives), and adversarial rows. The judge factory pins Gemini explicitly on every metric because DeepEval's default judge is paid OpenAI (Delta 1). One fixed canary golden with a known score detects judge drift before it can flap real gates. DeepEval's result cache is persisted in CI keyed on the golden-set hash, so re-runs of unchanged cases cost zero Gemini tokens; `deepeval test run` remains the runner because it adds caching, repeats, and parallelism over plain pytest (https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd).

### 3.10 The MCP mount, stateless (BUILT; one wiring note)

The Day-1 server already checks Host (fail-closed allowlist, the DNS-rebinding fix), then Origin (403), then the HS256 token (issuer, audience equal to this server, expiry), and tunnels the verified context through a contextvar with no token passthrough. Two things the survey confirms are ALSO already built, worth naming because they are the two classic mounting failures: the server is constructed with `stateless_http=True` (which is exactly where the protocol goes on 2026-07-28, Delta 3), and the MCP session manager's lifespan is wired into the FastAPI lifespan (`main.py` runs `session_manager.run()`), the number-one documented mounting failure when missed (https://github.com/modelcontextprotocol/python-sdk/issues/1367). The one remaining action item here is the dependency pin: `mcp>=1.27,<2` (Delta 3).

### 3.11 One request, end to end (how the layers compose)

A visitor asks "how do I rotate an API key?" on a host page. The gate middleware (tenants/gate.py, BUILT) checks the body size, looks up the widget key, exact-matches the Origin host against the key's allowlist, consults the rate limiter, and sanitizes the body to just the query; it stores a `VisitorRequestContext` on the request. The widget router (BUILT) pulls that context and calls the in-process adapter (agent/adapters.py, BUILT), which calls the core `answer` capability (agent/service.py, stub today, real Day 5). That function runs the pre-screen (guardrails, Day 6), then the module-scope agent with `AgentDeps(tenant_id, retriever)`. The agent's `retrieve` tool calls the Retriever PORT; the Weaviate ADAPTER binds `with_tenant(tenant_a)` before querying (Day 5); retrieved chunks come back datamarked. The agent drafts, the faithfulness check grades the draft against the chunks, and the typed `AnswerResult` flows back up: adapter, router, RFC 9457-safe response, streamed to the widget. Logfire holds the single trace; the tenant id was resolved exactly once, at the gate, and traveled as data the whole way. At no point did any layer below the router see a header, a token, or a raw request.

---

## 4. Security, gathered in one place

### 4.1 Per-door auth summary

| | Door A: owner | Door B: visitor | Door C: MCP |
|---|---|---|---|
| Credential | Supabase JWT, ES256 pinned, JWKS cached by kid | public widget key (an identifier, not a secret) | self-minted HS256 token, issuer and audience bound to this server |
| Tenant source | `app_metadata` only, never `user_metadata` | the widget-key row | the token claim |
| Extra checks | future-iat rejected, audience checked | body cap before parse, Origin/Referer exact-host, rate limit, sanitize-to-query | Host allowlist first (DNS rebinding), then Origin 403, no token passthrough |
| Status | BUILT + unit/integration tested | BUILT (rate limiter stub until Day 11) | BUILT (spike; core stubbed) |

### 4.2 Isolation enforcement points (belt, braces, and a test that sweeps)

Layer 1: structural. Weaviate native multi-tenancy makes an unscoped query impossible (an MT collection refuses operations without a tenant). Layer 2: database-enforced. RLS FORCED with WITH CHECK, app role unprivileged, tenant set per transaction through `tenant_txn` only. Layer 3: code discipline. The tenant travels as data in frozen contexts; there is one queue claim function, one cache-key builder (`key(tenant_id, kind, id)` when caching arrives), one storage-key builder with a tenant prefix. Layer 4: the Day-2 sweep test discovers tables dynamically, so forgetting a policy is a CI failure, not a code review hope. The known silent-break catalog this design answers: service_role misuse (the service never holds that key), owner-bypassing views (any view must declare `security_invoker = true`, checked in the sweep), SECURITY DEFINER functions (banned by default), missing WITH CHECK, unprotected new tables, vector-store filter omission, cache-key collisions, and jobs running without tenant context (the worker uses `tenant_txn`).

### 4.3 Secrets

Crown jewels: the Vertex service-account JSON, the Supabase service_role key (unused by the app; if an admin script ever needs it, it lives outside the service), the MCP signing secret, the app DB password. All live in typed `Settings` from env; the BUILT secret guard test asserts no secret field renders into OpenAPI or logs, and the BUILT log-hygiene integration tests assert tokens and widget keys never appear in structlog output. The browser holds exactly one string: the public widget key, whose safety is origin binding plus rate limit plus narrow scope, the same model Stripe publishable keys and Klaviyo public keys use.

### 4.4 Injection resistance and its honest limits

Four layers (Section 3.7): ingestion-time normalization, datamarking, a pre-screen, and the fused faithfulness verdict as the output backstop. The README states plainly that published attacks evade all commercial classifiers, so the claim is a measured block rate on a versioned adversarial set, not immunity. Indirect injection (instructions hidden in the owner's own documents) is treated as the primary threat, because OWASP LLM01's poisoned-RAG scenario is literally this product's shape.

### 4.5 Where the review gates sit

Every change runs the three skills (spec-review, senior-pass, security-review) before it is called done; CI runs the quick gate (ruff, format, mypy strict, unit) on every push, integration with real Postgres and Weaviate next, and the eval job separately. The spine tests (isolation sweep, poison-PDF survival, refusal, injection block rate, eval threshold) are named as such and protected: a change touching the spine must run them.

---

## 5. Process improvements (only where they serve the architecture)

Proposed, each small and surgical. (a) CLAUDE.md: fix the stale `instrument=True` line per Delta 2; add one line under non-negotiables, "tenant data access goes through `tenant_txn` and tenant-bound Weaviate handles ONLY"; add the three-lane gate wording per Delta 1; pin the dependency bounds (`pydantic-ai>=2,<3`, `mcp>=1.27,<2`) so a coding agent cannot resolve stale idioms from training data. (b) spec-review skill: its Step 2 stack list repeats claims that Delta 1 and Delta 4 correct; update the same two lines there, and add "check model names appear only in settings." (c) security-review skill: add two checklist items that current research elevated: "views must be `security_invoker`; SECURITY DEFINER requires written justification," and "no code path reads `request.state` below the router layer." (d) senior-pass skill: no change; the survey shows it is working (the Day-1 code passed it and the code is genuinely clean). (e) A one-page `docs/adr/` entry per accepted delta, so the repo itself carries the reasoning trail recruiters read. These edits happen only after the owner accepts the corresponding deltas, because the skills must mirror the spec, not lead it.

---

## 6. Reconciliation with the existing code (survey of 2026-07-02)

What already matches this blueprint and should not be touched: the domain-first layout, the three context types, the algorithm-pinned verifiers, the exact-host origin parsing shared by all doors, the Host-first MCP middleware, the AppError-to-problem-details mapping, the secret guard and log-hygiene tests, the three-layer test tree, and the CI shape (quick gate, then integration with real Postgres and Weaviate 1.38, then eval). The Day-1 code passed an independent survey with no layering violations found; the spine is real.

What changes when the relevant day arrives (none of it rework, all of it filling seams that were built for this): `retrieval/service.py`'s stub becomes the port plus Weaviate adapter (3.5); `agent/model.py`'s Protocol becomes `build_model` with `GoogleCloudProvider` (3.6), and the unused `ModelProvider` Protocol is deleted rather than kept as ceremony, per rule 3 and Delta 9 (owner call); `agent/service.py`'s stub `answer` gains its real body; `core/db.py` gains `tenant_txn`; `core/queue.py`, `ingestion/*`, `guardrails/*`, `eval/*` are net-new per the tree in 3.2.

Small debts the survey flagged, to fold into the next working session rather than a dedicated day: a mint-then-verify round-trip unit test for MCP tokens; a JWKS fetch timeout/failure test (the resolver is load-bearing and its network failure path is untested); a widget-key case-sensitivity test; and the observability wiring update from Delta 2. None is architectural; all are cheap.

---

## 7. What this means for the day plan (preview; full plan after approval)

The 12-day sequence in the locked spec survives intact; the architecture makes three refinements. Day 2 gains the dynamic sweep design (3.9), which is stronger than a hand-enumerated isolation test and no more work. Day 4 gains the one-hour Weaviate-hosting spike from Delta 8, so the Day-9 deploy cannot be ambushed. Day 7 builds the three-lane gate from Delta 1, which changes the red-to-green demo's mechanics slightly (drive the red through Lane 1 or far past Lane 2's margin) and makes the headline artifact reproducible by construction instead of by hope. Every day's build prompt will carry its slice of Section 3 as concrete structure guidance, so the coding agent starts from signatures, not prose.

---

## 8. Primary sources this blueprint relies on

Grouped; all fetched 2026-07-02 unless dated. FastAPI/PydanticAI: fastapi.tiangolo.com (bigger-applications, settings, events), github.com/zhanymkanov/fastapi-best-practices, pydantic.dev/docs/ai (changelog, google model, output, testing; v2.0.0 stable 2026-06-23). Data layer: postgresql.org/docs/current (ddl-rowsecurity, sql-createpolicy, functions-admin, sql-select SKIP LOCKED), supabase.com/docs (RLS best practices, database advisors, disabling prepared statements, storage file limits), docs.weaviate.io (multi-tenancy, tenant states, vector config, hybrid search; v1.38.0 announced 2026-06-09), pgbouncer.org/features. Eval/observability: deepeval.com/docs (metrics-dag, metrics-tool-correctness, unit-testing-in-ci-cd, flags-and-configs; v4.0.x June 2026), confident-ai.com DAG design post (2025-02-09), thinkingmachines.ai on inference nondeterminism (2025-09-10), anthropic.com statistical approach to evals (2024-11), logfire docs (fastapi, sampling, distributed tracing), pydantic.dev online-evals announcement (2026-04-30), docs.sentry.io (python tracing, shared environments). MCP: modelcontextprotocol.io 2025-11-25 changelog and authorization spec, blog.modelcontextprotocol.io 2026-07-28 RC (2026-05-21) and SDK betas (2026-06-29), python-sdk issues #1367 and #713. Widget: lit.dev (shadow DOM, styles), MDN (Cache-Control, CORS, custom elements), vite.dev build options, Zendesk and Atlassian widget CSP docs, Klaviyo public-key allowlist. Ingestion: pymupdf docs and issues #1507/#2907/#556, pymupdf.io hybrid-OCR post, ocrmypdf cookbook, artifex.com/licensing. Gemini/Vertex: docs.cloud.google.com/vertex-ai (models, quotas, safety filters, batch prediction, context caching), ai.google.dev (models 2026-06-30, media resolution, gemini-3). Injection: genai.owasp.org LLM01 and LLM08, arxiv.org/abs/2403.14720 (spotlighting, 2024-03), arxiv.org/abs/2504.11168 (guardrail evasion, 2025-04), arxiv.org/abs/2402.07867 (PoisonedRAG).

---

**STOP POINT.** Per the mandate, this blueprint pauses here for owner review. The decisions waiting on Dotun: accept or reject Deltas 1 through 7 and 9 (Deltas 1 and 9 each edit a locked-spec sentence; the rest are corrections and closures of open decisions, including the crawl-lane clarification under Delta 5), and note Delta 8 as a scheduled spike. On approval, Phase 3 produces `DAY_PLAN.md`: every remaining day with its goal, spec, non-negotiables, paste-ready autonomous build prompt, review steps, and that day's slice of this architecture as concrete code guidance.

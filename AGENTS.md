> This file mirrors `CLAUDE.md` verbatim so Codex and other AGENTS.md-aware tools read the same rules. `CLAUDE.md` is the source of truth; keep both in sync.

# CLAUDE.md

You are a senior engineer on THIS project. These rules are load-bearing. Follow them on every task. Full rationale lives in `Planning/senior_engineering_foundation.md`; the locked product spec is `Planning/BUILD_SPEC_LOCKED.md`. Where those disagree, the spec wins. Do not contradict either.

This file is mirrored as `AGENTS.md` so Codex reads the same rules. Keep both in sync.

## Goal

A multi-tenant embeddable AI support assistant: an owner feeds it their content (PDFs incl. scanned/image PDFs + a small site crawl), drops one script tag, and the widget answers visitors grounded only in that owner's content, refuses with an honesty verdict when it cannot ground, and resists prompt injection. The reliability/eval layer is the product. Posture: single-tenant-excellent (two tenants + a passing isolation test, scale path documented), not full multi-tenancy.

## Locked stack

PydanticAI on Python/FastAPI (one service: API + agent + ingestion worker). Gemini via Vertex AI for generation, vision, and embeddings. Weaviate (multi-tenancy on, hybrid search). Supabase/Postgres (RLS forced). DeepEval (DAG-metric gate + one agentic metric + online scorer). Logfire + Sentry. Remote Streamable-HTTP MCP (Origin-validated, bearer-token, scoped). React+Vite dashboard, Lit+Shadow-DOM widget. Free-tier hosting kept warm with a free keep-alive ping. GitHub Actions CI.

## Non-negotiables (the spine, protect on every change)

- Tenant isolation: tenant A cannot read/write tenant B, in BOTH Postgres and Weaviate. Proven by a test.
- Poison-PDF survival: a malformed PDF lands in the DLQ with a reason; the worker never crashes.
- Reproducible red-to-green eval gate: a bad change turns the DAG eval gate red, the fix turns it green, repeatably. Use the deterministic DAG metric so it does not flap.
- Deployed: the service is hosted, reachable, and shareable on request.

Never weaken any of these. If a change touches the spine, the spine tests run and pass.

## Owner adjustments (override the general plan)

- Gemini via Vertex AI only. Build the multi-provider abstraction (one narrow interface in `agent/`, documented fallback), but Gemini is the live model and we say so. Vertex is used only as the Gemini API, never for hosting.
- Demo is private. Deploy to a hosted URL, share on request. No public front door. Build-in-public is the narrative (failing evals, red CI, fixes), not a public app.
- UI is minimal. Dashboard is product-only: upload, status, results, trace link. Red-to-green is shown via the real CI run, not a custom eval UI.
- Cost discipline, not centerpiece: prompt caching, content-hash dedupe before any vision call, embedding cache, gated OCR. The only billing card anywhere is the Google Cloud one for Vertex credits; every other service stays free and card-free.

## Coding standards (enforce every time)

- Environment: uv. Commit `uv.lock`, pin Python. CI runs `uv sync --frozen`. Frontend: npm with committed lockfile, Node pinned.
- Lint + format: Ruff (`ruff check --fix` and `ruff format`) with the strict select set incl. `ASYNC`, `S`, `B`. Biome on the frontend (+ a thin ESLint flat config for react-hooks in the dashboard). Formatting is decided by the tool; never argue it.
- Types are the spec. mypy strict + Pydantic plugin (backend); TypeScript `strict` + `noUncheckedIndexedAccess` (frontend). Enforced in CI. The only escape hatch is a justified `# type: ignore[code]` with the specific code; never bare. Stale ignores are CI errors.
- Never block the event loop. `async def` for awaitable I/O; plain `def` only for fully-sync handlers (threadpool). Push blocking work off the loop: `asyncio.to_thread` for blocking I/O, a process pool for CPU-heavy work. PDF parsing runs in a separate, timeout-bounded process (crash isolation + CPU). The Ruff `ASYNC` rules partly enforce this; do not fight them.
- Module layout is domain-first, not file-type. Each domain (`tenants`, `ingestion`, `agent`, `retrieval`, `guardrails`, `eval`, `mcp`) owns its router, schemas, service, deps, exceptions. `core/` holds settings, logging, db, shared deps. `src/` layout, tests in a mirrored `tests/` tree.
- Tenant scoping is resolved per door, each from its own credential (see `docs/spec-amendments.md` A1, which supersedes the original single-`get_current_tenant` wording): owner JWT → `app_metadata`, visitor key → key row, MCP token → token claim, each producing its own typed context in `tenants/contexts.py`. Keep one scoping seam WITHIN a door; do not re-introduce a single cross-door `get_current_tenant`. Never weaken a door's resolver per route. API schemas are separate from internal/DB models; every route declares `response_model`.
- Agent: typed PydanticAI deps (`deps_type`/`RunContext`) and a validated `output_type` (the honesty verdict is a discriminated union, not free text and not an exception). Define the `Agent` at module scope.
- Config: one typed `Settings(BaseSettings)` via pydantic-settings. Import the settings object; never read `os.environ` scattered through code. App fails at startup if misconfigured. `.env.example` committed with dummies; `.env` never committed.
- Errors: an `AppError` hierarchy (`TenantAccessError`, `NotFoundError`, `IngestionError`, `GuardrailRefusal`, ...) raised in service/agent layers, mapped centrally to RFC 9457 problem-details responses. Fail loudly: no bare `except`, no catch-and-return-200, no silent `pass`. Catch only what you can handle, log with context, re-raise or convert. The one expected-failure path is the ingestion DLQ.
- Secrets server-side (Backend-for-Frontend). The widget holds only a public widget key; the server holds secrets and calls the model. The Supabase `service_role` key and the Vertex service-account JSON are crown jewels: never in the widget bundle, never in the browser, never in a CI log; host env + GitHub Actions secrets only.
- Observability: structlog rendering JSON, bound to tenant/request/trace id via contextvars. Logfire (`instrument_fastapi`, Agent `instrument=True`) so one run is one trace. Sentry initialized, low trace sample rate. Never log a secret or full document content; log ids and decisions.

## Testing

Three layers. Unit (pure logic, agent wired with PydanticAI `TestModel`, no LLM). Integration (httpx `AsyncClient` over `ASGITransport`, real Postgres + Weaviate in Docker; the isolation test and poison-PDF test live here). Eval (DeepEval golden set, DAG gate, marked `@pytest.mark.eval`, its own CI job). `asyncio_mode = "auto"`. Real Gemini calls only in the eval layer. Coverage is reported, not worshipped; the gate is "the spine is tested": isolation, poison-PDF, refusal, injection block, eval threshold.

## Agent working rules

- Types are the spec. Read and generate against them; let mypy/tsc be your fast feedback loop.
- Small, focused modules: each capability in one package you can hold whole.
- No comment rot. Meaningful names carry the what. Comment ONLY a non-obvious why (a workaround, a business rule, an ordering constraint). A comment that narrates the code is dead code; delete it. No dead code, no commented-out code.
- Clear naming over cleverness. DRY and reusable.
- Run the fast quick-gate before committing: `ruff check`, `ruff format --check`, `mypy`, unit tests. Keep `main` and `develop` green and deployable.
- Conventional Commits (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, ...). Make ATOMIC commits: one logical change per commit, each with a clear, descriptive message, so anyone can read the commit history neatly and follow what happened step by step.
- Two long-lived branches: `main` (stable) and `develop` (integration). NEVER commit directly to `main` OR `develop`. This is a hard rule. For every build day or feature, create a short-lived branch OFF `develop` (for example `day-3-pdf-spike`). When the work is done and self-reviewed (CI quick-gate and integration green, and all three review skills pass), open a pull request against `develop`. Do NOT merge the PR yourself; leave it open until the owner explicitly says to merge. If `develop` does not exist yet, create it off `main` first. If you have been committing directly to a long-lived branch, stop and start branching from the current day.

## HARD SELF-REVIEW (do not skip)

Before marking any unit of work done or opening a PR, run ALL THREE skills on the diff:

1. spec-review: does it match `BUILD_SPEC_LOCKED.md` and the day's artifact?
2. senior-pass: clean architecture, DRY, typed, tested, no comment rot, real error handling, nothing mediocre.
3. security-review: diff-driven application-security pass (auth, multi-tenant isolation, secrets, injection/SSRF, MCP token + no passthrough, error/info leak, abuse); BLOCKS on Critical/High.

Work is NOT finished until all three pass. If any flags something, fix it and re-run. No exceptions under deadline.

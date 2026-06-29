# Senior Engineering Foundation

**Prepared by:** Principal engineer review
**Date:** 2026-06-29
**For:** Dotun Loto
**Grounded in:** `BUILD_SPEC_LOCKED.md` (source of truth), `flagship_final_plan.md` (architecture and risk register), `kickoff_steps_and_prep.md` (Day 1/2 and accounts).

This document is the complete foundation the codebase must have in place at the start of building, before feature work begins, and the conventions every commit holds to. It is not a wish list. It is the floor a senior engineer would refuse to start without, plus the few places where I push past the defaults you named.

The owner named four things: linting, no comment rot, readable architecture, types. Those are correct and they are a floor. This document keeps all four and adds the rest of what "a codebase a senior engineer respects on sight, that AI agents can work in" actually requires: reproducible environments, a fast deterministic feedback loop, real test layers, secrets and supply-chain hygiene, observability conventions, error contracts, container discipline, and the agent-facing files that make Claude Code and Codex productive instead of guessing.

Voice rules carried through: plain English, short lines, no em dashes, name the choice not three options. Every recommendation gives the tool, the why, and the trade-off. Sources are real and cited inline.

A note on scope. This is a two-week, single-developer, AI-augmented build of one Python service plus a small React dashboard and a Lit widget. I have deliberately NOT gold-plated. Where a practice is real but does not earn its cost in this build (mutation testing, a monorepo tool, Vault, SBOM signing), I say so and say why, rather than pretending everything is mandatory. The test of every item below is: does it make the build finish faster, safer, or more credible to a senior reviewer. If not, it is out.

---

## 0. The principle that orders everything

A codebase has one job before it has features: make the right thing easy and the wrong thing loud. Every choice below serves that. Types make wrong data loud at the boundary. The linter makes sloppy code loud before commit. CI makes a regression loud before merge. The eval gate makes a quality drop loud before deploy. RLS and tenant scoping make a cross-tenant leak loud in a test instead of silent in production.

This matters doubly because the build is AI-augmented. An AI agent is a fast, confident, literal collaborator with no memory between sessions and no instinct for your intent. It thrives exactly where a strong junior thrives: a typed surface it can read as a spec, a fast feedback loop it can self-correct against, small modules it can hold in its head, and written-down rules it cannot guess. It fails exactly where a junior fails: silent ambiguity, stale comments it trusts, hidden global state, and "you just have to know" conventions. So the foundation that makes the codebase good for a senior reviewer is the same foundation that makes it good for the agent. They are not two goals. Anthropic's own context-engineering guidance says the same thing from the model side: load durable load-bearing facts up front, let the agent retrieve the rest just in time, and keep the signal high because performance degrades as context fills (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

---

## 1. Repository hygiene and layout

**Decision: a single repository, `src/` layout, one Python service plus two frontend packages as sibling folders. Not a monorepo tool.**

Top-level shape:

```
/
  backend/                 # the one Python service (API + agent + ingestion worker)
    src/app/               # importable package, src-layout
    tests/                 # mirrors src/app, tests live here not beside code
    pyproject.toml
    Dockerfile
    .dockerignore
  widget/                  # Lit + Vite library bundle
  dashboard/               # React + Vite app
  docs/
    adr/                   # architecture decision records
    architecture.md
  .github/workflows/       # CI
  CLAUDE.md                # agent entry point (symlinked or referenced as AGENTS.md)
  README.md
  .gitignore
  .pre-commit-config.yaml
```

**Why `src/` layout for the backend.** Putting the package under `src/app` instead of `app/` at the repo root forces tests to run against the installed package, not against loose files on the path. This catches "works on my machine because the cwd happens to be right" packaging bugs before they ship. It is the layout pytest's own docs recommend (https://docs.pytest.org/en/stable/explanation/goodpractices.html).

**Why tests in a `tests/` tree, not beside each module.** The spec says "tests beside the code," and I am pushing back on the literal reading. "Beside the code" should mean tests live with the service, in the same repo, mirroring the package structure, run on every commit. It should not mean a `_test.py` next to every source file. A separate `tests/` tree that mirrors `src/app/` keeps the shipped package clean (your Docker image and your published surface contain zero test code), makes coverage scoping trivial (`--cov=app`), and is the convention pytest documents. The intent behind "beside the code" is "tests are not an afterthought in a separate repo or a separate phase," and the mirrored `tests/` tree satisfies that intent fully. This is the right way; the literal co-location is the weaker default.

**Three packages, one repo, no monorepo tool.** The backend, widget, and dashboard are independent build targets in different languages. Keep them in one git repo for one history, one set of issues, one CI. Do not reach for Nx, Turborepo, or a workspace orchestrator. For three packages built by one person in two weeks, a monorepo tool is pure overhead with no payoff. The trade-off you accept: you run three install/build commands instead of one orchestrated graph. That is fine at this size. Document the swap in the README as a scale note.

**`.gitignore` from day one,** generated for Python, Node, and your OS, plus explicit entries for `.env`, `.venv`, `*.local`, `node_modules`, `dist`, `.coverage`, `htmlcov`. The single most damaging hygiene failure is committing a `.env` or a service-account JSON. Section 7 makes that loud; `.gitignore` makes it unlikely in the first place.

---

## 2. Dependency and environment management

**Decision: uv (Astral) for the backend. Commit `uv.lock`. Pin everything.**

uv is the consensus default for new Python projects in 2026. It is a single Rust binary that does resolution, virtual-env management, and installs 10 to 100x faster than pip, and it surpassed Poetry in adoption (https://docs.astral.sh/uv/, https://github.com/astral-sh/uv). For an AI-augmented build the speed is not a vanity metric: a faster install is a faster feedback loop, and the agent re-runs the loop constantly.

**Why a committed lockfile, and why pin.** `uv.lock` is a universal lockfile. One file resolves correct versions across OS, architecture, and Python version via environment markers, so your Mac dev box and the Linux CI runner and the Docker build install byte-identical dependency trees (https://docs.astral.sh/uv/concepts/projects/sync/). Without a committed lock, versions drift between machines and over time, and a passing CI run stops meaning anything. In CI you run `uv sync --frozen` so the build fails if the lock is stale rather than silently resolving something new (https://docs.astral.sh/uv/guides/integration/github/). This is also a supply-chain control: a pinned lock is the thing a dependency-audit scans, and an unexpected version change shows up as a lockfile diff in review.

**Trade-off considered.** Poetry is mature and many teams know it. I still choose uv because it is faster, the lockfile model is cleaner, and the Docker story (section 9) is first-class. The only reason to pick Poetry would be an existing team standard, which you do not have.

**Frontend: npm with a committed `package-lock.json`,** Node version pinned in `.nvmrc` and in `engines`. Same principle: lock the tree, reproduce it everywhere. Do not introduce pnpm or yarn for two small frontend packages; npm is sufficient and universal.

**Python version pinned** in `.python-version` and `requires-python` in `pyproject.toml`. The agent and CI must agree on the interpreter.

---

## 3. Linting, formatting, and import sorting

**Decision: Ruff for the backend, as both linter and formatter. Biome for the frontend.**

**Ruff replaces the entire legacy Python stack.** One Rust binary does what flake8, isort, black, pyupgrade, pydocstyle, and bandit-style security rules used to need six tools to do, at roughly 100x the speed, and it is what FastAPI and Pydantic themselves use (https://docs.astral.sh/ruff/faq/, https://github.com/astral-sh/ruff). Run `ruff check` (lint, with `--fix`) and `ruff format` (format) as two steps.

Ruff's defaults are only `E` and `F`, so you must opt into a real rule set. Enable, in `[tool.ruff.lint] select`:

- `E`, `W` pycodestyle, `F` Pyflakes (correctness floor)
- `I` isort (import sorting, replaces a whole separate tool)
- `B` flake8-bugbear (real bug patterns, e.g. mutable default args)
- `UP` pyupgrade (keeps syntax modern for the pinned Python)
- `S` bandit (security: flags `subprocess` misuse, hardcoded secrets, unsafe deserialization, all directly relevant to your PDF-subprocess and tenant code)
- `C4` comprehensions, `SIM` simplify, `N` pep8-naming (readability and consistency)
- `ASYNC` flake8-async (catches blocking calls inside async code, which is exactly your event-loop risk from section 6)

Rules reference: https://docs.astral.sh/ruff/rules/. The formatter is Black-compatible, so it is not a bikeshed; line length, quotes, and trailing commas are decided by the tool and never argued about. That determinism is itself a feature for an AI agent: there is one correct formatting and the tool produces it.

**Frontend: Biome, not ESLint plus Prettier, for the baseline.** Biome is one Rust tool that lints and formats TypeScript at roughly 10 to 20x ESLint-plus-Prettier speed, and for new projects in 2026 it is the recommended default (https://biomejs.dev/, https://devtoolbox.blog/biome-vs-eslint-prettier-2026-2/). The honest caveat: Biome cannot yet do type-aware lint rules or the React-hooks plugin (https://betterstack.com/community/guides/scaling-nodejs/biome-eslint/). For the **widget** (Lit, no React) Biome alone is enough. For the **dashboard** (React) add a thin ESLint flat config carrying only `eslint-plugin-react-hooks` on top of Biome's formatting and base lint. That is the pragmatic 2026 split, and it keeps the fast tool doing the bulk of the work.

---

## 4. Static type checking and how strict

**Decision: mypy in strict mode with the Pydantic plugin for the backend. TypeScript `strict` plus `noUncheckedIndexedAccess` for the frontend. Types are non-negotiable and enforced in CI.**

This is the heart of the owner's "typed Python end to end," and it is the single highest-leverage thing for both senior credibility and AI productivity. Types are a machine-readable spec. Without them the agent guesses at what a function expects and what shape comes back; with them it reads the contract and generates against it, with far fewer fix cycles (https://www.builder.io/blog/typescript-vs-javascript). Type errors surface in the editor before tests, before commit, before review. That is essentially free, instant feedback, and it is the loop the agent self-corrects against (https://www.aihero.dev/essential-ai-coding-feedback-loops-for-type-script-projects).

**Why mypy and not ty (yet).** Astral's `ty` is dramatically faster and checks unannotated bodies by default, but as of mid-2026 it is still beta with lower typing-spec conformance than mypy and Pyright (https://docs.astral.sh/ty/, https://pydevtools.com/handbook/explanation/how-do-mypy-pyright-and-ty-compare/). For the gate that fails your build, use mypy: it is what Pydantic and FastAPI use, it has the Pydantic plugin, and it is the conventional, defensible choice a reviewer expects. You may run `ty` locally for fast pre-save feedback, but mypy is the authority. This is a place where the newest tool is not yet the right tool, and saying so is the senior call.

**Strictness, from Pydantic's own documented config** (https://docs.pydantic.dev/latest/integrations/mypy/):

```toml
[tool.mypy]
plugins = ["pydantic.mypy"]
strict = true                 # the whole strict bundle on
warn_redundant_casts = true
warn_unused_ignores = true
disallow_any_generics = true
no_implicit_reexport = true

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

`strict = true` turns on `disallow_untyped_defs`, `disallow_incomplete_defs`, `no_implicit_optional`, and the rest as a set. The Pydantic plugin makes your settings and models type-check correctly and catches construction errors. FastAPI itself ships with `strict = true` plus this plugin, so this is not aggressive, it is standard for a serious FastAPI codebase.

**The one allowed escape hatch is a typed, justified `# type: ignore[code]`** with the specific error code, never a bare ignore. `warn_unused_ignores = true` means a stale ignore becomes a CI error, which prevents ignore-rot the same way you prevent comment-rot.

**Frontend strictness.** Set `strict: true` (it bundles eight checks including `strictNullChecks` and `noImplicitAny`) and add `noUncheckedIndexedAccess`, which makes array and record access return `T | undefined` so you handle the missing case (https://www.typescriptlang.org/tsconfig/strict.html, https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html). The simplest way to get all of this is to extend `@tsconfig/strictest` (https://www.npmjs.com/package/@tsconfig/strictest).

---

## 5. Testing strategy

**Decision: three layers (unit, integration, eval), pytest with `asyncio_mode = "auto"`, httpx AsyncClient over ASGITransport for API tests, a mirrored `tests/` tree, coverage reported but gated pragmatically.**

**Layer 1, unit.** Pure functions and isolated logic: the per-page PDF router heuristics, the content-hash dedupe, the UUIDv5 helper, the prompt-injection pre-screen logic, the verdict types. Fast, no network, no model. These are where the agent gets the tightest loop, so they should be the most numerous.

**Layer 2, integration.** The API surface tested through the real ASGI app. Use httpx `AsyncClient` with `ASGITransport(app=app)`, not the sync `TestClient`. It respects the full async lifecycle, routes in-process with no real network, and is FastAPI's documented async-test pattern (https://fastapi.tiangolo.com/advanced/async-tests/). Drive it with pytest-asyncio set to `asyncio_mode = "auto"` so you do not decorate every test (https://pypi.org/project/pytest-asyncio/). This is the layer that holds your two non-negotiables: the **tenant isolation test** (tenant A cannot read or write tenant B, in both Postgres and Weaviate) and the **poison-PDF survival test** (a malformed file lands in the DLQ with a reason instead of crashing the worker) live here, hitting real Postgres and Weaviate in Docker.

**Layer 3, eval.** DeepEval golden set run as `deepeval test run`, with the deterministic DAG metric as the gate decision so it does not flap (per the spec and https://deepeval.com/docs/metrics-dag). This is a distinct layer with its own marker and its own CI job, because it is slower, it touches the model, and it is the product's headline. Mark it (`@pytest.mark.eval`) so the fast unit/integration layers can run without it during normal development and the agent's inner loop stays fast.

**Crucial for AI-augmented work: test the agent without the LLM.** PydanticAI ships `TestModel` and `FunctionModel` precisely so you can unit-test agent wiring, tool calls, and output shapes with no model call, no cost, no latency, no nondeterminism, via `Agent.override(model=...)` (https://ai.pydantic.dev/testing/, https://ai.pydantic.dev/api/models/test/). Use `TestModel` for the deterministic unit tests of the agent and reserve real Gemini calls for the eval layer only. This keeps the inner loop fast and free, which matters when an agent is iterating.

**Fixtures and layout.** A `conftest.py` at the `tests/` root holds shared fixtures: a transactional test-DB session that rolls back per test, an authenticated AsyncClient, a seeded two-tenant fixture, a sample-PDF fixture set (including one image-only page and one poison file). Mirror `tests/` to `src/app/` so any module's tests are findable by path.

**Coverage: measure with pytest-cov, report `term-missing` and html, but do not worship a number.** A pragmatic target is roughly 80 to 90 percent on application code (https://docs.pytest.org/en/stable/explanation/goodpractices.html, supporting: https://pythoneo.com/testing-fastapi-applications/). I push back on a 100 percent gate: it pressures people to write hollow tests for trivial lines and slows a two-week build. Gate instead on "the spine is tested": the isolation test, the poison-PDF test, the refusal path, the injection block, and the eval threshold must pass. Coverage is a dashboard, not the gate. Mutation testing (mutmut, cosmic-ray) is real and excellent and out of scope here; note it as a maturity step.

---

## 6. Async conventions

**Decision: `async def` for I/O handlers, never block the event loop, and push every blocking job off it explicitly.**

This is a correctness issue specific to your stack, and it is where a subtle mistake degrades the whole service silently. FastAPI runs on one event loop. An `async def` handler that calls a blocking library stalls every concurrent request, not just its own (https://fastapi.tiangolo.com/async/).

The rules:

- Use `async def` for handlers doing awaitable I/O (DB queries via an async driver, HTTP calls, the agent run).
- Use plain `def` only when the whole handler is a synchronous library call; FastAPI runs `def` handlers in a threadpool so they do not block the loop (https://fastapi.tiangolo.com/async/).
- **Never call blocking code inside an `async def`.** PDF parsing (PyMuPDF), embedding computation, and any CPU-heavy work are blocking. Push them off the loop with `await asyncio.to_thread(...)` for I/O-bound blocking, and a `ProcessPoolExecutor` for CPU-bound work so the GIL does not serialize you (https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread, https://www.starlette.io/concurrency/).
- The poison-PDF subprocess from the risk register is the strongest version of this rule: PDF parsing runs in a **separate, timeout-bounded process** both because a malformed PDF can segfault the MuPDF C library (uncatchable in Python) and because it is CPU-heavy. One pattern solves both the crash-isolation and the event-loop problem.

The Ruff `ASYNC` rule set (section 3) statically catches many blocking-in-async mistakes, so this convention is partly enforced by the linter, not just by discipline.

---

## 7. Configuration and secrets management

**Decision: pydantic-settings for all config, twelve-factor environment config, `.env.example` committed and `.env` never, service-role and Vertex keys treated as the crown jewels.**

**Typed config via pydantic-settings.** A single `Settings(BaseSettings)` class reads every config value from the environment with type validation and defaults, parses complex values as JSON, and fails at startup if a required value is missing or the wrong type (https://docs.pydantic.dev/latest/concepts/pydantic_settings/). This is config as a typed contract: the app cannot boot misconfigured, and the agent reading `settings.py` sees exactly what the service needs. Import the settings object, never read `os.environ` scattered through the code.

**Twelve-factor: config lives in the environment, strictly separated from code.** The litmus test is that the repo could be made public at any instant without leaking a credential (https://12factor.net/config). Anything that varies between local, CI, and deployed (database URLs, the Vertex service-account path, Supabase keys, the Logfire and Sentry tokens) is an environment value, not a constant in code.

**`.env.example` is committed and documents every required key with dummy values. `.env` is gitignored and never committed.** This is the direct application of the open-source litmus test. The agent reads `.env.example` to know what to set; nobody ever commits real values.

**The two most dangerous secrets in this build,** called out explicitly because the kickoff doc already flagged them: the Supabase `service_role` key (bypasses RLS, so leaking it defeats tenant isolation) and the Vertex service-account JSON (the only thing that can spend real money). These never reach the browser, never reach the widget bundle, never appear in a CI log, and live only in host env and GitHub Actions secrets. This is the Backend-for-Frontend posture the spec already locked: the widget holds only a public widget key, the server holds the secrets, the server calls the model (https://blog.gitguardian.com/stop-leaking-api-keys-the-backend-for-frontend-bff-pattern-explained/).

**Trade-off on secret managers.** A managed secret store (AWS Secrets Manager, HashiCorp Vault) with rotation is the production-grade answer (https://www.strongdm.com/blog/secrets-management). For this two-week, free-tier, card-free build it is out of scope: host environment variables plus GitHub Actions secrets are the correct, proportionate choice. Name the secret-manager-plus-rotation upgrade in the README scale section so the reviewer sees you know the production answer and chose the right one for the demo.

---

## 8. Logging, observability, and error handling

### 8.1 Structured logging

**Decision: structlog rendering JSON, bound to request and trace context via contextvars.** stdlib `logging` handles output plumbing well but not structure; structlog sits in front, runs each event through a processor pipeline, renders JSON, and its `contextvars` integration gives you request-scoped, async-safe structured logs in FastAPI (https://www.structlog.org/en/stable/standard-library.html). Every log line carries the tenant id, request id, and trace id, so a single grep across logs, Logfire, and Sentry reconstructs one request. Never log a secret or full document content; log identifiers and decisions.

### 8.2 Tracing and metrics

**Decision: Logfire over OpenTelemetry, two-line FastAPI auto-instrumentation, PydanticAI instrumented, Sentry for errors.** Logfire is an opinionated wrapper around OpenTelemetry, so you get a vendor-neutral standard underneath and no lock-in (https://logfire.pydantic.dev/docs/why/, https://opentelemetry.io/docs/languages/python/). FastAPI instrumentation is `logfire.configure()` plus `logfire.instrument_fastapi(app)` (https://logfire.pydantic.dev/docs/integrations/web-frameworks/fastapi/). PydanticAI auto-instruments with `Agent(..., instrument=True)`, so one run is one trace spanning retrieval, the model call, and the verdict (https://ai.pydantic.dev/logfire/). This is the "everything is one trace" property the spec promised, and it is nearly free to wire.

**Sentry for errors,** auto-enabled by the FastAPI integration on `sentry_sdk.init()`, capturing exceptions with stack traces and request context, `traces_sample_rate` kept low to stay inside the free quota (https://docs.sentry.io/platforms/python/integrations/fastapi/). Correlate Sentry trace ids with the structured logs and Logfire spans.

### 8.3 Error handling

**Decision: a custom exception hierarchy in the service layer, a small set of registered handlers mapping them to HTTP responses in the RFC 9457 problem-details format, and a strict no-swallow rule.**

Define `AppError` and subclass it: `TenantAccessError`, `NotFoundError`, `IngestionError`, `GuardrailRefusal`, and so on. The service and agent layers raise these typed errors. A handful of `@app.exception_handler(...)` functions translate them to HTTP responses centrally, instead of `try/except` scattered through every route (https://fastapi.tiangolo.com/tutorial/handling-errors/, https://github.com/zhanymkanov/fastapi-best-practices).

**Serve errors as RFC 9457 problem details.** The current standard error contract is a JSON body with `type`, `title`, `status`, `detail`, `instance`, served as `application/problem+json` (https://www.rfc-editor.org/rfc/rfc9457.html). Build one envelope, use it everywhere, so the dashboard, the widget, and the MCP client all parse errors the same way. A consistent error shape is also a gift to the agent: it can handle failures uniformly instead of pattern-matching ad-hoc shapes.

**Fail loudly. Never swallow.** No bare `except:`, no catch-and-return-200, no silent `pass`. Catch only what you can handle, log with context, and re-raise or convert to a typed domain error (https://dev.to/buffolander/building-robust-error-handling-in-fastapi-and-avoiding-rookie-mistakes-ifg). The Ruff `B` and `E722` rules flag bare excepts, so this is partly enforced by the linter. The one place a caught failure is correct is the ingestion DLQ path, where a poison file is an expected outcome routed to a recorded failure, not a swallowed error.

**Typed outcomes where failure is expected, not exceptional.** The honesty verdict (grounded answer with sources, or honest refusal) is a typed PydanticAI `output_type`, a discriminated union, not an exception. Exceptions are for the unexpected; the refusal is an expected, modeled outcome. This is the right boundary between "return a typed result" and "raise."

---

## 9. Security, supply-chain, and containerization

### 9.1 Dependency and secret scanning

**Decision: `uv audit` (or pip-audit) in CI, gitleaks at the commit gate and in CI, GitHub push protection on, Dependabot for updates with human review.**

- **Known-CVE scanning:** `uv audit` reads the lockfile and queries the OSV database, faster than pip-audit and also flagging archived or quarantined packages (https://astral.sh/blog/uv-audit). Run it on every CI run. This is why the pinned lockfile from section 2 matters: it is the artifact being audited.
- **Secret scanning:** gitleaks is rule-and-entropy based, instant, and fully offline, which makes it the right fit for both the pre-commit hook and a CI diff scan (https://github.com/gitleaks/gitleaks). Turn on GitHub's native push protection as a backstop that blocks known-provider key patterns at push time (https://secrails.com/blog/trufflehog-vs-gitleaks-github-secret-scanning-guide). Defense in depth: the hook catches it before commit, push protection catches it before it reaches GitHub, the CI scan catches it before merge.
- **Updates:** Dependabot is GitHub-native and free (https://docs.renovatebot.com/bot-comparison/). Enable it, but do not auto-merge: dependency auto-update PRs are a real malware-delivery surface, so a human reviews the lockfile diff (https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/).
- **Pin CI action versions to commit SHAs,** not floating tags, so a compromised tag cannot inject a malicious step (same source).

**Out of scope, named honestly:** SBOM generation and signing, TruffleHog verified-history scans, and a full SCA platform are real practices that do not earn their cost in a two-week solo build. The lockfile, OSV audit, gitleaks, and push protection are the proportionate set.

### 9.2 Containerization and local dev

**Decision: multi-stage Dockerfile built with uv, a slim or distroless final image, non-root user, a `.dockerignore` that excludes `.venv`, and `docker compose` for the full local stack.**

- **Multi-stage build with uv.** Copy a pinned uv binary in (`COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/`), sync dependencies in a build stage with `--no-editable`, and copy only the resulting venv into a minimal final stage (https://docs.astral.sh/uv/guides/integration/docker/). Smaller, faster, fewer CVEs.
- **`.dockerignore` excluding `.venv`** is the single highest-impact line: uv creates a local venv you must not ship to the build daemon or bake into the image (same source). Also exclude `tests/`, `.git`, `__pycache__`, and `node_modules`.
- **Non-root user.** Create an `app` user and `USER app` so the container does not run as root (https://docs.roxautomation.com/linux/docker_best_practices/).
- **Slim or distroless final base.** A debian-slim or distroless final image removes the shell and package manager that most container CVEs exploit (https://www.joshkasuboski.com/posts/distroless-python-uv/). For a two-week build, debian-slim is the pragmatic floor; distroless is the upgrade if time allows.
- **`UV_COMPILE_BYTECODE=1`** so bytecode compiles at build time, not on first request, helping the cold-start budget the risk register tracks (https://docs.astral.sh/uv/guides/integration/docker/).
- **`docker compose` for local dev** brings up Postgres, Weaviate (multi-tenancy enabled, hybrid config), and the API together with one command. This is the reproducible local environment, and it is also what the integration tests run against. The agent reads the compose file to understand the runtime topology.

---

## 10. FastAPI and PydanticAI module structure and boundaries

**Decision: domain-driven (feature-based) packages, not file-type folders. Each domain owns its router, schemas, service, dependencies, and exceptions. The agent and ingestion worker are their own domains.**

The widely-cited reference is zhanymkanov's fastapi-best-practices, and its central rule is to structure by domain, not by file type (https://github.com/zhanymkanov/fastapi-best-practices). A flat `routers/`, `schemas/`, `services/` split looks tidy with two features and turns into cross-folder spaghetti with eight. Feature packages keep everything about one capability in one place:

```
src/app/
  core/            # settings, logging, db sessions, security, shared deps
  tenants/         # router, schemas, service, deps, exceptions
  ingestion/       # upload, queue, the per-page PDF router, DLQ, worker
  agent/           # the PydanticAI agent, tools, typed deps, output types
  retrieval/       # tenant-scoped hybrid search over Weaviate
  guardrails/      # injection pre-screen, faithfulness, refusal verdict
  eval/            # DeepEval golden set, DAG metric, online scorer
  mcp/             # the Streamable-HTTP MCP server, origin + token checks
  main.py          # app factory, router includes, instrumentation
```

**Why this serves the agent and the reviewer.** Small, focused modules each map to one job. An agent asked to change retrieval opens `retrieval/` and holds the whole concern in context; it does not have to load five file-type folders to understand one capability. A reviewer reads the directory listing and understands the system. This is the "readable architecture" the owner named, made concrete.

**Boundaries that matter:**

- **API schema is separate from the internal model.** The Pydantic request/response models in `schemas.py` are the public contract; the internal/DB models are not exposed. Every route declares `response_model` so output is filtered to the contract and internals never leak (https://fastapi.tiangolo.com/tutorial/response-model/).
- **Tenant scoping is one shared dependency,** `get_current_tenant`, injected into every tenant-touching router, raising `TenantAccessError` on mismatch. Isolation is enforced in one place, not re-implemented per route. This is the seam the Day-2 test proves.
- **PydanticAI typed deps and typed output.** The agent receives the tenant's Weaviate handle and services through PydanticAI's typed dependency injection (`deps_type`, accessed via `RunContext`), and returns a validated `output_type`, never free text (https://ai.pydantic.dev/dependencies/, https://ai.pydantic.dev/output/). Define the `Agent` at module scope and import it (https://ai.pydantic.dev/agents/). Typed deps and typed output are what make the agent testable with `TestModel` and readable as a spec.
- **The extensible seam the spec asks for** is the multi-provider model interface: one interface, Gemini behind it, with a documented fallback. Keep that interface narrow and in `agent/`. That is the "scalable-by-design" boundary, and it is one file, not a framework.

---

## 11. API design conventions

**Decision: versioned path prefix, plural resource nouns, explicit response models and status codes, RFC 9457 errors, cursor pagination where lists can grow.**

- **Version in the path:** mount everything under `/v1`. URL-path versioning is explicit and the most practical; bump on breaking changes (https://fastapi.tiangolo.com/tutorial/bigger-applications/).
- **Resources are plural nouns, verbs are HTTP methods:** `POST /v1/documents`, `GET /v1/documents/{id}`, hierarchy via the path (https://fastapi.tiangolo.com/tutorial/path-params/).
- **Explicit `status_code` using `fastapi.status` constants,** not bare integers, so intent is readable (https://fastapi.tiangolo.com/tutorial/response-status-code/).
- **One error envelope, RFC 9457** (section 8.3).
- **Cursor (keyset) pagination, not offset,** for any list that grows under concurrent writes (document lists, eval results), because offset drifts when rows shift (https://github.com/zhanymkanov/fastapi-best-practices).
- **OpenAPI is generated, so keep it honest:** accurate `summary`, `description`, `tags`, and response models on every route. The generated `/docs` is part of what a reviewer clicks, and an MCP client and the agent both read the schema.

---

## 12. Pre-commit hooks and what runs in them

**Decision: the pre-commit framework, a tight fast hook set, mypy in CI not in the hook.**

The hook gate must stay under about ten seconds or developers (and you, under deadline) start using `--no-verify` and the gate is dead (https://pre-commit.com/, https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835). Run:

- **ruff** (lint with `--fix`) and **ruff-format**, from `astral-sh/ruff-pre-commit` (https://github.com/astral-sh/ruff-pre-commit)
- **gitleaks** and **detect-private-key** (secret scanning at the gate)
- **hygiene hooks** from pre-commit-hooks: `end-of-file-fixer`, `trailing-whitespace`, `check-merge-conflict`, `check-case-conflict`, `check-toml`, `check-yaml`, `check-added-large-files`, `debug-statements` (https://github.com/pre-commit/pre-commit-hooks)
- **frontend:** biome check on staged frontend files

**Why mypy is in CI, not the hook.** mypy is slow and needs the full resolved environment; pinning it in an isolated pre-commit venv gives false results and blows the ten-second budget. Type-checking belongs in CI and the editor. This is the documented community position and it keeps the commit gate fast (https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835). The trade-off: a type error can be committed locally and is caught in CI seconds later rather than at commit. That is the right trade for loop speed.

---

## 13. CI gates and ordering

**Decision: GitHub Actions, a fast quick-gate that fails early, then a heavier gate that depends on it, with the eval gate as a distinct job. Cache uv. Pin action SHAs.**

Order matters because cheap checks should fail before expensive ones run (https://oneuptime.com/blog/post/2026-02-02-github-actions-job-dependencies/view):

**Quick gate (runs first, fails fast):**
1. `uv sync --frozen` (fails on a stale lock)
2. `ruff check` and `ruff format --check` (lint and format)
3. `mypy` strict (types)
4. unit tests (pytest, no model, no external services)
5. `uv audit` and gitleaks (supply chain and secrets)

Lint, type, and audit can run in parallel; they are independent. Use `fail-fast: true` so a trivial failure cancels the rest (https://medium.com/@Modexa/12-github-actions-moves-for-faster-cheaper-ci-6bed9064e0f6).

**Heavy gate (`needs:` the quick gate):**
6. integration tests against Postgres and Weaviate service containers (this is where the isolation test and the poison-PDF test run)
7. the eval gate: `deepeval test run` with the DAG metric threshold, as its own step so its red/green is the headline artifact

**Cache uv** with `astral-sh/setup-uv`'s built-in cache so installs are not re-downloaded every run (https://docs.astral.sh/uv/guides/integration/github/). **Pin every action to a commit SHA** (section 9.1).

This ordering is also what makes the Day-8 red-to-green story reproducible: a deliberately bad change fails the eval gate specifically, visibly, in the named job, and the fix turns it green. The deterministic DAG metric is what keeps that gate from flapping (spec, https://deepeval.com/docs/metrics-dag).

---

## 14. Documentation: README and ADRs

**Decision: a README essay, an `architecture.md` with a diagram, and an `docs/adr/` directory of short decision records in Nygard format.**

**The README is the front door for the human reviewer.** It is the build-in-public artifact and the recruiter's first read. It carries: the one-sentence product, the architecture overview, how to run it locally (one `docker compose up`), the real numbers from the week (eval scores, injection block rate, latency), and an honest scale-and-hardening section naming exactly what is built for two tenants versus operated at scale, the MCP OAuth that is documented versus demonstrated, and the secret-manager and SBOM upgrades deferred on purpose. That honesty section is itself a senior signal: it shows you know the production answer and chose the right scope for the demo.

**ADRs capture the architecturally significant decisions** so the why survives. Use Michael Nygard's format (Title, Status, Context, Decision, Consequences), one short markdown file per decision in `docs/adr/NNNN-title.md` (https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions, https://adr.github.io/). The decisions worth a record here: single-tenant-excellent over full multi-tenancy, one Python service over the edge/app split, scoped MCP over a full OAuth authorization server, the DAG metric for a non-flapping gate, uv and Ruff and mypy as the toolchain. When the format benefits from recording the alternatives weighed, use MADR, which extends Nygard with an explicit considered-options section (https://adr.github.io/madr/). ADRs are also high-value for the agent: they are the durable "why we did it this way" the model cannot infer from code.

---

## 15. Commit and branch conventions

**Decision: Conventional Commits, trunk-based development with short-lived branches.**

**Conventional Commits 1.0.0:** `<type>(scope): description`, types `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `style` (https://www.conventionalcommits.org/en/v1.0.0/). This gives a readable history, enables an automated changelog, and maps cleanly to the build-in-public narrative (the commit log itself tells the story of the week). It is also a clean instruction for the agent: it knows exactly how to format the commit it writes.

**Trunk-based, not git-flow.** Short-lived feature branches merged frequently into `main`, each through a CI-gated PR. For a solo, two-week build, git-flow's long-lived develop and release branches are pure ceremony with no payoff, and trunk-based is the DORA-associated practice for high-performing teams (https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development). The PR gate is where CI, the spec-review skill, and the senior-standards skill run, so even solo work goes through review before it hits main. Keep `main` always green and always deployable.

---

## 16. What makes this codebase work for AI coding agents

This is its own section because it is half the point, and most of it is the same hygiene that serves the human reviewer, made explicit.

**A `CLAUDE.md` at the repo root, kept short and load-bearing.** Anthropic's own guidance: document the common build and test commands, the code-style and naming conventions, repo etiquette, and the non-obvious gotchas, and keep it concise because it is loaded into context on every turn (https://www.anthropic.com/engineering/claude-code-best-practices). Write rules as direct imperatives and include explicit negative rules, because absent a "never," the agent defaults to the most common pattern it knows (https://code.claude.com/docs/en/memory). For this build the negatives that matter: never put a secret in the widget bundle, never call blocking code in an `async def`, never weaken a tenant-scoping check, never add a comment that narrates the code, never commit `.env`. Keep it under a few hundred lines and refine it as the build teaches you what the agent gets wrong.

**Adopt the AGENTS.md convention so the file is portable.** AGENTS.md is the emerging tool-neutral standard, "a README for agents," adopted across tens of thousands of repos and supported by Codex, Cursor, Aider, and others (https://agents.md/, https://www.infoq.com/news/2025/08/agents-md/). Since the build uses both Claude Code and Codex, keep the content in one file and reference it from both names so both agents read the same rules instead of drifting apart. This is a small thing that prevents two agents following two different sets of conventions.

**Types as guardrails (sections 4 and 10).** The strict mypy and TypeScript config is the single biggest agent-productivity lever. Types are the spec the agent reads and the instant feedback it self-corrects against (https://www.builder.io/blog/typescript-vs-javascript, https://www.aihero.dev/essential-ai-coding-feedback-loops-for-type-script-projects).

**A fast deterministic feedback loop (sections 5, 12, 13).** The agent's value is proportional to how fast and how truthfully it can verify its own work. Fast unit tests with `TestModel` (no LLM in the loop), a sub-ten-second commit gate, and a deterministic eval gate that does not flap are what let the agent iterate without burning your time or the Gemini credits. A flaky gate is worse than no gate for an agent, because it trains the agent (and you) to ignore red.

**Small, focused modules (section 10).** Each capability in one package the agent can load whole. This is the same property that makes the code readable to a human, which is the point: there is one good structure, not an agent structure and a human structure.

**No comment rot, comments only for the non-obvious why.** Comments rot because engineers maintain code and forget the comment, so an old comment is likely a lying comment, and a lying comment is worse than none, especially to an agent that trusts it (https://dev.to/actocodes/self-documenting-code-vs-comments-lessons-from-maintaining-large-scale-codebases-52im). The rule the spec already states is correct and I keep it verbatim: meaningful names carry the what, comments are reserved for the non-obvious why (a workaround, a business rule, an ordering constraint), and a comment that narrates the code is dead code. Clean Code's lineage says the same: a comment is often an apology for code that should have been clearer, so clean the code instead (https://www.bensampica.com/blog/cleancode3/).

**Clear naming over cleverness.** A name that states intent is the cheapest, most durable documentation, readable identically by the reviewer and the agent. This is not a soft preference; it is the mechanism that makes the no-comment rule work.

---

## 17. The minimum bar, as a checklist

Before any feature work, these exist and pass:

- Repo with `src/` layout, `.gitignore`, `docker compose` bringing up Postgres and Weaviate
- uv with a committed `uv.lock`, pinned Python, `.env.example` committed and `.env` ignored
- Ruff (lint plus format) with the strict select set; Biome on the frontend
- mypy strict plus the Pydantic plugin; TypeScript `strict` plus `noUncheckedIndexedAccess`
- pytest with `asyncio_mode = "auto"`, httpx AsyncClient over ASGITransport, a mirrored `tests/` tree, pytest-cov reporting
- pydantic-settings as the one typed config object
- structlog JSON logging, Logfire instrumentation wired, Sentry initialized
- An `AppError` hierarchy and RFC 9457 error handlers
- pre-commit with ruff, ruff-format, gitleaks, hygiene hooks
- GitHub Actions: quick gate (sync, lint, type, unit, audit, secrets) then heavy gate (integration, eval), uv cached, action SHAs pinned
- A domain-structured `src/app/` with the tenant-scoping dependency in one place
- `CLAUDE.md` (referenced as AGENTS.md), a README skeleton, `docs/adr/` with the first records
- Conventional Commits, trunk-based, main always green

That is the foundation. Everything in the twelve-day plan builds on it, and none of it is optional, because each item turns a class of silent failure into a loud one.

---

## 18. Where I pushed past the defaults

Stated plainly, because the brief asked for it.

1. **"Tests beside the code" should mean a mirrored `tests/` tree, not a `_test.py` next to every file (section 1).** The intent is "tests are first-class and run on every commit," which the mirrored tree satisfies while keeping the shipped package and Docker image free of test code and keeping coverage scoping clean. The literal co-location is the weaker reading.

2. **Coverage is a dashboard, not a gate (section 5).** A 100 percent coverage gate breeds hollow tests and slows a two-week build. Gate on the spine being tested (isolation, poison-PDF survival, refusal, injection block, eval threshold) and treat the coverage number as information. This is the senior call against a common cargo-cult metric.

3. **mypy now, not ty; mypy in CI, not in pre-commit (sections 4 and 12).** The newest type checker (Astral's ty) is not yet conformant enough to be the gate, so use mypy and say why; and mypy belongs in CI rather than the commit hook so the commit gate stays under ten seconds and never gets bypassed. Both are deliberate choices against "use the newest" and "run everything in pre-commit."

4. **Things I deliberately left out, and named so (sections 5, 7, 9).** Monorepo tooling, a secret manager with rotation, SBOM signing, TruffleHog history scans, and mutation testing are all real and all out of scope for this build. Calling them out as deferred-on-purpose in the README is itself a senior signal: it proves you know the production answer and right-sized the demo, which reads stronger than either omitting them silently or half-building them.

5. **Two additions the brief did not name (sections 6, 16).** The Ruff `ASYNC` rule set plus the explicit never-block-the-event-loop convention, because for a FastAPI service doing PDF parsing and embeddings this is a real and subtle failure mode that a linter can partly enforce; and the AGENTS.md portability convention, because this build uses both Claude Code and Codex and a single shared rules file stops the two agents from drifting into two different sets of conventions.

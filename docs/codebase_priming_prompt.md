> Historical, kept as-is. Predates ADR-0006: this prompt names `get_current_tenant`, which was later removed in favor of per-door request contexts (spec amendment A1 → ADR-0006).

# Codebase Priming Prompt (paste into Claude Code)

You are setting up an empty repository for a multi-tenant embeddable AI support assistant (Python/FastAPI + PydanticAI backend, React+Vite dashboard, Lit+Vite widget). This task is PRIMING ONLY: the full toolchain, config, structure, and empty wiring. Do NOT build any product features. Every package and module you create is an empty, importable, wired stub. By the end the quick-gate must actually pass and CI must be green on this empty scaffold.

Two documents are the source of truth. Read both before you touch anything, and do not contradict either:
- `Planning/senior_engineering_foundation.md` (the toolchain, standards, and layout decisions)
- `CodebasePrep/CLAUDE.md` (the rules file to place at the repo root)

Where I leave a detail unspecified below, follow the foundation doc's exact choice. Use plain English in everything you write. No em dashes anywhere. Use the tool's default formatting and never argue line length or quotes.

Work in the ordered phases below. Commit after each phase using Conventional Commits (`chore`, `build`, `ci`, `docs`, `test`, `feat` for the first scaffold of a wired package). Keep `main` green.

---

## Phase 0: Read and confirm

1. Read `Planning/senior_engineering_foundation.md` and `CodebasePrep/CLAUDE.md` in full.
2. Restate, in 8 to 12 lines, the locked decisions you are about to implement (uv, Ruff strict select, mypy strict + Pydantic plugin, three test layers, pre-commit fast hooks, CI quick-gate then heavy, pydantic-settings, domain-first layout, structlog/Logfire/Sentry, docker compose, AGENTS.md mirror). Do not start building until this is stated.

## Phase 1: Repo skeleton and hygiene

1. Create this top-level shape (foundation doc section 1):
   ```
   /
     backend/
       src/app/
       tests/
       pyproject.toml
       Dockerfile
       .dockerignore
     widget/
     dashboard/
     docs/
       adr/
       architecture.md
     .github/workflows/
     CLAUDE.md
     AGENTS.md
     README.md
     .gitignore
     .editorconfig
     .pre-commit-config.yaml
     docker-compose.yml
     Makefile
   ```
2. `git init` if not already a repo. Default branch `main`.
3. Write a `.gitignore` generated for Python, Node, and macOS, plus explicit entries: `.env`, `.venv`, `*.local`, `node_modules`, `dist`, `.coverage`, `htmlcov`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`.
4. Write `.editorconfig`: UTF-8, LF line endings, final newline, trim trailing whitespace; 4-space indent for Python, 2-space for JSON/YAML/TS/JS/Markdown.
5. Place `CodebasePrep/CLAUDE.md` verbatim at the repo root as `CLAUDE.md`. Create `AGENTS.md` that mirrors it. Make `AGENTS.md` reference the same content (either a copy kept in sync or a note pointing both names at one source). State in `AGENTS.md` that it mirrors `CLAUDE.md` and both must stay in sync.
6. Commit: `chore: scaffold repo skeleton and hygiene files`.

## Phase 2: uv project, pinned Python, src layout

1. In `backend/`, create a uv project with `pyproject.toml`. Pin Python in `.python-version` and set `requires-python` to match (use a current stable, e.g. 3.12 unless the foundation doc names another).
2. Use `src/` layout: the importable package is `src/app`. Configure the build so `app` installs from `src/`.
3. Add the runtime and dev dependency groups the build needs (FastAPI, pydantic, pydantic-settings, pydantic-ai, structlog, logfire, sentry-sdk, httpx; dev: ruff, mypy, pytest, pytest-asyncio, pytest-cov, pre-commit). Pin nothing by hand; let uv resolve.
4. Run `uv sync` so a real `uv.lock` is produced. Commit `uv.lock`.
5. Add a `py.typed` marker in `src/app/` so the package ships as typed.
6. Commit: `build: initialize uv project with pinned python and src layout`.

## Phase 3: Ruff, mypy, pytest config

1. In `backend/pyproject.toml`, configure Ruff as BOTH linter and formatter. `[tool.ruff.lint] select` must include exactly the foundation doc's strict set: `E`, `W`, `F`, `I`, `B`, `UP`, `S`, `C4`, `SIM`, `N`, `ASYNC`. Configure the formatter (Black-compatible defaults). Add a per-file ignore so test files may use `assert` (ignore `S101` under `tests/`).
2. Configure mypy strict with the Pydantic plugin, copied from the foundation doc section 4:
   ```toml
   [tool.mypy]
   plugins = ["pydantic.mypy"]
   strict = true
   warn_redundant_casts = true
   warn_unused_ignores = true
   disallow_any_generics = true
   no_implicit_reexport = true

   [tool.pydantic-mypy]
   init_forbid_extra = true
   init_typed = true
   warn_required_dynamic_aliases = true
   ```
3. Configure pytest: `asyncio_mode = "auto"`, test paths `tests`, and register markers `integration` and `eval`. Configure pytest-cov to report `term-missing` and html scoped to `--cov=app`, but do NOT set a hard coverage-fail threshold (coverage is a dashboard, not the gate).
4. Run `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy src` to confirm the empty tree is clean. Fix anything that is not.
5. Commit: `build: configure ruff strict select, mypy strict with pydantic plugin, pytest asyncio auto`.

## Phase 4: Domain-first package skeleton (empty wired packages)

Create the domain-first layout under `src/app/` (foundation doc section 10). Every file is a real, importable, typed stub with no feature logic. Each domain package gets `__init__.py` and empty-but-typed `router.py`, `schemas.py`, `service.py`, `deps.py`, `exceptions.py` as appropriate (an empty `APIRouter()` with no routes is fine).

1. `core/` containing:
   - `settings.py`: one typed `Settings(BaseSettings)` via pydantic-settings. Include fields the locked stack needs as typed settings with sensible defaults or `None` (database URL, Weaviate URL, Vertex/Gemini config path, Supabase keys, Logfire token, Sentry DSN, widget public key). Provide a cached `get_settings()` accessor. The app must fail at startup if a required value is missing. Import this object everywhere; never read `os.environ` elsewhere.
   - `logging.py`: structlog configured to render JSON, bound to tenant/request/trace id via contextvars. Provide a `configure_logging()` entrypoint. Inert without external keys.
   - `observability.py`: Logfire init stub (`logfire.configure()` + `instrument_fastapi(app)`) and Sentry init stub (`sentry_sdk.init()` with low `traces_sample_rate`), both reading from `Settings`. Wired but inert when keys are absent (guard on the setting being present).
   - `db.py`: an async DB session dependency stub (no real engine wiring needed beyond a typed placeholder that reads the URL from settings).
   - `errors.py`: the `AppError` hierarchy (`AppError`, `TenantAccessError`, `NotFoundError`, `IngestionError`, `GuardrailRefusal`) and an RFC 9457 problem-details handler stub. Define one typed problem-details envelope model and a small set of `@app.exception_handler(...)` registration functions that map `AppError` subclasses to `application/problem+json` responses. No business logic.
   - `deps.py`: the single shared `get_current_tenant` dependency stub. It is the ONE place tenant scoping lives; it raises `TenantAccessError` on mismatch. Leave the body as a typed stub that returns a placeholder tenant or raises, clearly marked as the wiring seam, not a feature.
2. Domain packages, each an empty wired package: `tenants/`, `ingestion/`, `agent/`, `retrieval/`, `guardrails/`, `eval/`, `mcp/`. Each owns its own `router.py` (empty `APIRouter`), `schemas.py`, `service.py`, `deps.py`, `exceptions.py` as relevant. In `agent/`, add a one-file narrow multi-provider model interface stub (one interface, Gemini named as the live model in a docstring or type), per the owner adjustment. No agent logic.
3. `main.py`: the app factory. It calls `configure_logging()`, builds `Settings`, configures observability, registers the RFC 9457 exception handlers, includes every domain router under a `/v1` prefix, and returns the `app`. It must import cleanly and the app must construct without external services.
4. Comment rule: no narrating comments. A comment exists only for a non-obvious why. Names carry the what.
5. Run `uv run mypy src` and `uv run python -c "from app.main import create_app; create_app()"` (or equivalent) to prove it imports and constructs.
6. Commit: `feat: scaffold domain-first package skeleton with core wiring stubs`.

## Phase 5: Three-layer test tree (mirrored, eval separated)

1. Create the mirrored `tests/` tree with three layers: `tests/unit/`, `tests/integration/`, `tests/eval/`. Mirror the `src/app/` package structure beneath them where it helps.
2. `tests/conftest.py`: shared fixture stubs (a placeholder transactional DB session fixture, an authenticated httpx `AsyncClient` over `ASGITransport(app=app)` fixture, a two-tenant seed fixture). These are stubs that import and are collectible, not feature tests.
3. Add one trivial passing test per layer so collection works and the quick-gate is green:
   - `tests/unit/test_smoke.py`: asserts the app factory imports and constructs.
   - `tests/integration/test_smoke.py`: marked `@pytest.mark.integration`, a minimal `AsyncClient` call against the empty app (e.g. an OpenAPI/docs route returns 200), skipped cleanly if services are needed.
   - `tests/eval/test_smoke.py`: marked `@pytest.mark.eval`, a trivial placeholder so the eval layer exists and is separated.
4. Configure markers so the inner loop runs unit only by default and the eval layer is excluded unless selected. Document the exact commands in the Makefile (Phase 9).
5. Run `uv run pytest tests/unit` and confirm green. Confirm `uv run pytest -m eval` selects only the eval layer.
6. Commit: `test: scaffold three-layer mirrored test tree with smoke tests`.

## Phase 6: pre-commit (fast hooks only)

1. Write `.pre-commit-config.yaml` with the fast hooks only (foundation doc section 12). mypy and tests do NOT go in pre-commit; they run in CI.
   - `astral-sh/ruff-pre-commit`: `ruff` (with `--fix`) and `ruff-format`.
   - `gitleaks/gitleaks` (secret scan) and `detect-private-key`.
   - `pre-commit/pre-commit-hooks` hygiene: `end-of-file-fixer`, `trailing-whitespace`, `check-merge-conflict`, `check-case-conflict`, `check-toml`, `check-yaml`, `check-added-large-files`, `debug-statements`.
2. Pin each hook repo to a tagged release rev.
3. Run `uv run pre-commit run --all-files` and fix anything it flags until it passes clean.
4. Add a short comment block at the top of the file stating that mypy and tests run in CI, not here, on purpose (keep the gate under ten seconds).
5. Commit: `ci: add fast pre-commit hooks (ruff, ruff-format, gitleaks, hygiene)`.

## Phase 7: GitHub Actions CI (quick-gate first, green on empty repo)

1. Write `.github/workflows/ci.yml`. Pin EVERY action to a full commit SHA, not a floating tag. Use `astral-sh/setup-uv` with its built-in cache and run `uv sync --frozen` in every job.
2. Job `quick-gate` (runs first, `fail-fast: true`):
   1. `uv sync --frozen` (fails on a stale lock)
   2. `uv run ruff check`
   3. `uv run ruff format --check`
   4. `uv run mypy src`
   5. `uv run pytest tests/unit`
   6. gitleaks diff scan and a dependency audit step (`uv audit` or `pip-audit`), non-blocking if the tool is unavailable on the empty tree but wired.
3. Job `integration` (`needs: [quick-gate]`): brings up Postgres and Weaviate service containers and runs `uv run pytest -m integration`. On the empty scaffold this must still pass (smoke test or a clean skip), so the job is green.
4. Job `eval` (`needs: [quick-gate]`): runs `uv run pytest -m eval` as its own distinct job so its red/green is a separate headline artifact. Green on the empty scaffold.
5. The quick-gate MUST actually pass on this empty scaffold. Run every quick-gate command locally to confirm before committing. The whole point is green CI on commit one.
6. Commit: `ci: add github actions quick-gate then integration and eval jobs`.

## Phase 8: docker compose for local dev

1. Local data stack = local Supabase in Docker (Postgres + Auth) plus Weaviate in Docker.
   a. Run `supabase init` to create the `supabase/` config, then `supabase start` to boot the local Supabase stack in Docker (Postgres, Auth/GoTrue, Studio). Capture the local values it prints: the API URL, anon key, service_role key, and DB connection string. These are local dev values (rotatable), so capturing them is fine.
   b. Write `docker-compose.yml` bringing up Weaviate with multi-tenancy enabled and hybrid search configured, plus a service entry for the API. Use pinned image tags. Postgres comes from local Supabase, so do NOT duplicate a Postgres service here. Environment values come from `.env` (gitignored).
2. Write `backend/Dockerfile` as a multi-stage build using a pinned uv binary (`COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/`), `uv sync --frozen --no-editable` in a build stage, a slim final base, a non-root `app` user, and `UV_COMPILE_BYTECODE=1`.
3. Write `backend/.dockerignore` excluding `.venv`, `tests/`, `.git`, `__pycache__`, `node_modules`.
4. Confirm `docker compose config` parses cleanly. (Do not require the stack to fully boot in this priming task; the file must be valid and complete.)
5. Commit: `build: add docker compose local stack and multi-stage backend dockerfile`.

## Phase 9: Settings, env, Makefile, README, ADRs

1. Write `.env.example` at the repo root documenting EVERY key the `Settings` class reads, with dummy values and a one-line comment each. THEN also create a real, gitignored `.env` populated with the actual LOCAL values: the local Supabase API URL, anon key, service_role key, and DB connection string from `supabase start`, plus the local Weaviate URL (e.g. `http://localhost:8080`). These are local-only, rotatable dev values, so writing them is fine. `.env` stays gitignored and is never committed.
2. Write a `Makefile` (or uv task entries) with the common commands. Provide at least: `install` (`uv sync`), `lint` (`uv run ruff check`), `format` (`uv run ruff format`), `typecheck` (`uv run mypy src`), `test` (`uv run pytest tests/unit`), `test-integration`, `test-eval`, `quick-gate` (ruff check + ruff format --check + mypy + unit tests, in order), `up` (`supabase start && docker compose up -d`), `down` (`docker compose down && supabase stop`). Keep `quick-gate` identical to the CI quick-gate steps so local and CI agree.
3. Write a `README.md` skeleton: one-sentence product, locked stack, how to run locally (`supabase start`, then `docker compose up`), the common commands, and an honest "scale and hardening, deferred on purpose" section naming the deferred items from the foundation doc (monorepo tooling, secret manager with rotation, SBOM signing, TruffleHog history scans, mutation testing).
4. Write `docs/architecture.md` skeleton (overview + a placeholder for the diagram) and add the first ADRs in `docs/adr/` in Nygard format for the toolchain decisions already made (uv, Ruff, mypy, the single-service domain-first layout, the DAG metric gate). Short files, `docs/adr/NNNN-title.md`.
5. Commit: `docs: add env example, makefile tasks, readme skeleton, and first adrs`.

## Phase 10: Frontend placeholders

Scaffold minimal placeholders for both frontends so the structure is visible and wired, but do NOT build UI features.

1. `dashboard/`: a minimal React+Vite TypeScript scaffold with `tsconfig` extending the strictest config (`strict` + `noUncheckedIndexedAccess`), Biome configured for lint+format, and a thin ESLint flat config carrying only `eslint-plugin-react-hooks` on top of Biome. `package.json` with a committed `package-lock.json`, Node pinned via `.nvmrc` and `engines`. An empty app shell that builds.
2. `widget/`: a minimal Lit+Vite TypeScript library scaffold with the same strict TS config and Biome alone (no React, so no ESLint hooks plugin). Committed lockfile, Node pinned. An empty widget that builds.
3. If a full frontend scaffold would balloon this priming task, you MAY defer the frontends to a stub `README.md` in each folder that states exactly what goes there and the chosen tooling (Vite, Biome, strict TS, the ESLint-hooks caveat for the dashboard). If you defer, justify briefly in one line. Prefer at least the buildable placeholders if time allows, since the foundation doc names them as part of the floor.
4. Commit: `feat: scaffold frontend placeholders for dashboard (react) and widget (lit)` (or `docs:` if deferred to stub READMEs).

## Phase 11: Make the quick-gate green and run the self-review skills

1. Run the full local quick-gate exactly as CI runs it: `uv sync --frozen`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`, `uv run pytest tests/unit`. Every step must pass. Fix until green.
2. Run `uv run pre-commit run --all-files` and confirm clean.
3. Confirm `docker compose config` parses and both frontends build (or their stub READMEs exist, if deferred).
4. Run the spec-review skill: confirm the scaffold matches `BUILD_SPEC_LOCKED.md` and the foundation doc, and that nothing here builds a feature ahead of plan.
5. Run the senior-pass skill: confirm clean architecture, typed everywhere, no comment rot, real error-contract wiring, no dead code, no mediocre stubs that will rot. Fix anything either skill flags, then re-run both. Priming is NOT done until both pass.
6. Final commit if anything changed: `chore: finalize priming, quick-gate green and self-review passed`.

## Definition of done

- uv project with committed `uv.lock`, pinned Python, `src/` layout.
- Ruff strict select (incl. `ASYNC`, `S`, `B`) as linter and formatter; mypy strict + Pydantic plugin.
- pytest asyncio auto mode, three-layer mirrored test tree, eval layer marked and separated.
- pre-commit fast hooks only (ruff, ruff-format, gitleaks, hygiene); mypy and tests in CI.
- GitHub Actions: quick-gate first, then integration and eval jobs, `uv sync --frozen`, SHA-pinned actions, green on the empty repo.
- pydantic-settings typed `Settings`, `.env.example` with dummies, `.gitignore`, `.editorconfig`.
- Domain-first skeleton (`tenants`, `ingestion`, `agent`, `retrieval`, `guardrails`, `eval`, `mcp`) plus `core/`, the single `get_current_tenant` dependency, the `AppError` hierarchy and RFC 9457 handler stub.
- structlog JSON logging, Logfire + Sentry init stubs reading from `Settings`, wired but inert.
- docker compose local stack (Postgres + Weaviate multi-tenancy + hybrid) and multi-stage Dockerfile.
- README skeleton, `CLAUDE.md` at root, `AGENTS.md` mirror, `docs/adr/` first records.
- Makefile/uv tasks for install, lint, format, typecheck, test, quick-gate, up/down.
- Frontend placeholders (or justified deferral stubs).
- Quick-gate passes locally and in CI on the empty scaffold; Conventional Commits throughout; spec-review and senior-pass both pass.

Do not start feature work. Stop when priming is done and report what was created, the green quick-gate output, and anything you deferred with its justification.

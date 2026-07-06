# Honest Agent

A multi-tenant embeddable AI support assistant. An owner feeds it their content
(PDFs, including scanned and image PDFs, plus a small site crawl), drops one
script tag on their site, and the widget answers visitors grounded only in that
owner's content, refuses with an honest verdict when it cannot ground an answer,
and resists prompt injection. The reliability and evaluation layer is the product.

> Status: priming scaffold. The toolchain, config, structure, and empty wiring
> are in place and the quick-gate is green; feature work has not started.

## Locked stack

- **Agent / API**: PydanticAI on Python + FastAPI, one service (API + agent + ingestion worker).
- **Model**: Gemini via Vertex AI for generation, vision, and embeddings. One narrow multi-provider seam in `agent/`, with Gemini as the only live model.
- **Vectors**: Weaviate (multi-tenancy on, hybrid search).
- **Relational + auth**: Supabase / Postgres (RLS forced).
- **Eval**: DeepEval (deterministic DAG-metric gate + one agentic metric + online scorer).
- **Observability**: Logfire (OpenTelemetry) + Sentry.
- **MCP**: remote Streamable-HTTP server, Origin-validated, bearer-token, scoped.
- **Frontend**: React + Vite dashboard, Lit + Shadow-DOM widget.
- **CI**: GitHub Actions, quick-gate then integration and eval jobs.

## Repository layout

```
backend/        the one Python service (src/app, mirrored tests/)
dashboard/      React + Vite dashboard (placeholder)
widget/         Lit + Vite widget library (placeholder)
docs/           architecture.md, adr/, and the planning source-of-truth docs
.github/        CI workflows
```

The backend is domain-first: `tenants`, `ingestion`, `agent`, `retrieval`,
`guardrails`, `eval`, `mcp`, each owning its own router and schemas, plus `core/`
for settings, logging, observability, the db seam, and the error contract. Tenant
scoping is resolved per door: owner JWT, visitor widget key, and MCP token each
produce their own typed context.

## Run it locally

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, and the
[Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
# 1. Bring up the local data stack (Supabase Postgres + Auth, and Weaviate).
make up

# 2. Capture the local Supabase values and write your .env.
cp .env.example .env
supabase status            # copy API URL, anon key, service_role key, DB URL into .env

# 3. Install backend dependencies.
make install

# 4. Run the fast gate.
make quick-gate
```

Then run the API with `uv --directory backend run uvicorn app.main:create_app --factory --reload`.

## Common commands

| Command | What it does |
| --- | --- |
| `make install` | `uv sync` the backend |
| `make lint` | `ruff check` |
| `make format` | `ruff format` |
| `make typecheck` | `mypy src` (strict) |
| `make test` | unit tests |
| `make test-integration` | integration tests (needs the stack up) |
| `make test-eval` | the eval layer |
| `make quick-gate` | lint + format check + types + unit, exactly as CI runs them |
| `make up` / `make down` | start / stop the local data stack |

Install the fast commit gate once with `uv --directory backend run pre-commit install`.

## Scale and hardening, deferred on purpose

This is a single-developer build scoped to single-tenant-excellent (two tenants
plus a passing isolation test, scale path documented, not operated). The following
are real production practices deliberately left out as out-of-scope for this build,
named here so the choice is explicit rather than an omission:

- **Monorepo tooling** (Nx, Turborepo): three packages built by one person do not earn an orchestrator. Three install/build commands instead.
- **A secret manager with rotation** (Vault, AWS Secrets Manager): host env + GitHub Actions secrets are the proportionate choice; the rotation upgrade is the production answer.
- **SBOM generation and signing**: the lockfile plus an OSV audit is the proportionate supply-chain control here.
- **TruffleHog verified-history scans**: gitleaks at the commit gate and in CI plus GitHub push protection covers the demo.
- **Mutation testing** (mutmut, cosmic-ray): excellent and out of scope; coverage is reported, and the gate is "the spine is tested" (isolation, poison-PDF, refusal, injection block, eval threshold).

See `docs/adr/` for the toolchain decision records and `docs/architecture.md` for
the system overview.

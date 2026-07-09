# Codebase Map

A living, terse index of `backend/src/app` (plus scripts, migrations, tests). One line per module and per public symbol. Update on every add/rename/move/delete. Stubs are tracked in `docs/STUB_LEDGER.md`.

## core/ — settings, db, errors, shared plumbing
- **core/settings.py** — the one typed config object; import `get_settings`, never `os.environ`; reads only `backend/.env` (per-component, ADR: no repo-root env).
  - `EMBEDDING_DIM = 768` — module-level FIXED constant (not a Settings field, not env-overridable); coupled 1:1 to the `chunks.embedding vector(N)` column and schema-match tested (ADR-0007).
  - `Settings` — all env-driven config: owner + app_user DB URLs, Weaviate, JWT/JWKS, MCP token + allowed origins/hosts, `generation_model`/`embedding_model`/`gcp_location`/`gcp_project` (Vertex, ADR-0007, env-overridable), `owner_jwks_refresh_cooldown_seconds` with a 60s minimum, visitor body cap, secrets.
  - `SECRET_SETTINGS_FIELDS`, `secret_values(settings)` — the secret registry + currently-configured secret strings (non-leak guard).
  - `get_settings()` — cached `Settings` singleton.
- **core/db.py** — the unprivileged asyncpg pool and the single tenant-scoped path.
  - `create_db_pool(settings)`, `close_db_pool(pool)` — app_user pool lifecycle (direct connection).
  - `tenant_txn(pool, tenant_id)` — the ONLY tenant-data path; sets the RLS tenant via a bind param, fails closed.
- **core/errors.py** — the AppError hierarchy mapped to RFC 9457 problem-details.
  - `AppError` base; `BadRequestError` 400, `AuthenticationError` 401, `TenantAccessError` 403, `NotFoundError` 404, `PayloadTooLargeError` 413, `RateLimitedError` 429, `ServiceUnavailableError` 503 (upstream dependency down, e.g. JWKS fetch), `IngestionError`/`GuardrailRefusal` 422.
  - `ProblemDetail` — the RFC 9457 envelope; `problem_response(...)`, `app_error_response(error, instance)` — build it; `register_error_handlers(app)` — wire AppError -> problem-details.
- **core/origins.py** — exact-host matching for the visitor gate and MCP.
  - `origin_host(v)`, `host_allowed(v, hosts)` — Origin host + allowlist; `authority_host(v)`, `authority_allowed(v, hosts)` — bare `Host` header host + allowlist (DNS-rebinding defence).
- **core/bearer.py** — `parse_bearer(header)` — parse `Authorization: Bearer` (shared by owner + MCP).
- **core/logging.py** — structlog JSON config: `configure_logging()`, `bind_request_context(...)`.
- **core/observability.py** — `configure_observability(app, settings)` — Logfire + Sentry init.
- **core/deps.py** — `Tenant` — small tenant value type (used by the two-tenant test seed).
- **core/content_length.py** — safe `Content-Length` parsing, shared by both body-cap gates.
  - `parse_content_length(value)` — int or None; raises `BadRequestError` on malformed/overlong/non-ASCII input instead of letting a raw `ValueError` from `int()` escape as a 500.
  - `enforce_content_length_cap(request, max_body_bytes, limit_message)` — parse + cap check -> a 400/413 `Response`, or `None` to proceed; the one place both the owner and visitor gates enforce their cap so the pattern cannot diverge or get half-fixed.
- **core/paths.py** — `path_under_prefix(path, prefix)` — segment-boundary path match (`path == prefix` or `startswith(prefix + "/")`), so a sibling route like `/v1/tenants2` is not wrongly pulled into a gate scoped to `/v1/tenants`. Used by both body-cap gates.

## tenants/ — the three doors' tenant resolution + widget store
- **tenants/contexts.py** — the three per-door request contexts (never collapsed): `OwnerRequestContext`, `VisitorRequestContext`, `ExternalCallerContext`.
- **tenants/owner_auth.py** — owner Supabase JWT verification (door A).
  - `JwksFetcher` — typed callable for fetching JWKS entries.
  - `JwksKeyResolver` — JWKS by kid, cached; refetch on miss is COOLDOWN-THROTTLED (default 300s, minimum 60s) with a bounded negative cache storing SHA-256 digests of unknown kids, so a random-kid flood cannot amplify into one fetch per request or retain raw attacker-controlled key-id text; a `threading.Lock` serializes the miss path (thread-safe under the `asyncio.to_thread` worker-thread model — see `get_owner_context`); a fetch failure converts to `ServiceUnavailableError` (503), never a raw exception. Throttle is per-process (FOLLOWUPS.md #3). `OwnerTokenVerifier` — ES256, iss/aud/exp, tenant from `app_metadata` only.
  - `build_owner_verifier(settings)`, `bearer_token(request)`, `get_owner_context(request)` (FastAPI dependency).
- **tenants/owner_gate.py** — owner-door body-size cap middleware (defense-in-depth, door A).
  - `install_owner_body_cap(app, path_prefix, max_body_bytes)` — delegates to `core/content_length.enforce_content_length_cap`. The guarded `path_prefix` is NOT hard-coded: `create_app` derives it from the tenants router's own mounted path (`/v1` + `tenants_router.prefix`), so a router rename moves the cap with it instead of silently unguarding the routes; it matches on the segment boundary (`core/paths.path_under_prefix`), so `/v1/ingestion` and siblings like `/v1/tenants2` are excluded. DECLARED-header-only, does not measure actual received bytes (FOLLOWUPS.md #2).
- **tenants/gate.py** — visitor widget-key gate middleware (door B).
  - `VisitorGate` — body cap -> key lookup -> exact-host Origin allowlist -> rate limit -> sanitize-to-query; `install_visitor_gate(app, provide_gate)` — scoped to its `/v1/widget` prefix on the segment boundary (`core/paths.path_under_prefix`); delegates its declared-length precheck to `core/content_length.enforce_content_length_cap` before buffering the body (FOLLOWUPS.md #1: an absent/chunked length still buffers the full body before `VisitorGate`'s real-bytes cap applies).
- **tenants/widget_keys.py** — the public widget-key store: `WidgetKeyRecord`, `WidgetKeyStore` (Protocol), `InMemoryWidgetKeyStore`, `PostgresWidgetKeyStore`.
- **tenants/rate_limit.py** — `RateLimiter` (Protocol) + `AllowAllRateLimiter` (STUB, ledger #4).
- **tenants/router.py** — `read_owner_identity` — placeholder owner route `GET /v1/tenants/me`.
- **tenants/widget_router.py** — `widget_answer` — `POST /v1/widget/answer`, gate context -> in-process core.
- **tenants/schemas.py** — `OwnerIdentity` — owner route response model.

## ingestion/ — PDF spike (per-page router + subprocess crash boundary + DLQ)
- **ingestion/errors.py** — `PoisonDocumentError` — a document that must go to the DLQ, carrying only a safe reason.
- **ingestion/pdf/models.py** — typed shapes across the subprocess boundary: `PageSource` (native/ocr/vision), `PageContent`, `ExtractionResult`, `ExtractionOk`/`ExtractionFailure` (the stdout envelope).
- **ingestion/pdf/router.py** — per-page router: native text -> gated OCR -> vision.
  - `route_page(page, run_ocr, describe_vision, cache)` — routing + SHA-256 vision dedupe; `run_ocr_tesseract(page)` — real Tesseract OCR; `StubVisionDescriber`, `build_vision_describer(settings)` — vision STUB (ledger #1), model name from Settings.
- **ingestion/pdf/extract.py** — child-process extractor entrypoint: `extract(path)`, `main()`.
- **ingestion/pdf/isolate.py** — `extract_isolated(path, timeout_s)` — parent side: subprocess + timeout -> `PoisonDocumentError`.
- **ingestion/pipeline.py** — DLQ-shaped spike orchestration: `DocumentStatus`, `ProcessedDocument`, `process_document(...)`, `process_batch(...)`.
- **ingestion/router.py** — EMPTY (Day 4 upload/queue endpoints).

## agent/ — core capability + adapters (stubbed)
- **agent/schemas.py** — honesty output types: `Source`, `GroundedAnswer`, `HonestRefusal`, `Verdict` (union), `AnswerResult` (answer + fused verdict).
- **agent/service.py** — `answer(tenant_id, query)` — STUB (ledger #3); the verdict is always fused.
- **agent/adapters.py** — `answer_in_process(context)` (widget), `answer_for_external_caller(context, query)` (MCP); no token passthrough.
- **agent/model.py** — `ModelProvider` (Protocol) — the multi-provider seam; Gemini via Vertex is the only live model (becomes `build_model` on Day 5).
- **agent/router.py** — EMPTY.

## retrieval/
- **retrieval/service.py** — `retrieve(tenant_id, query)` — STUB (ledger #2, Day 5 hybrid search).
- **retrieval/weaviate.py** — Weaviate tenancy: `tenant_name(id)`, `connect(settings)`, `bootstrap_chunks(client, tenant_ids)` (two tenants, auto-create off), `TenantChunks` (tenant-bound handle so an unscoped query is impossible).
- **retrieval/router.py** — EMPTY.

## mcp/ — door C
- **mcp/tokens.py** — `McpTokenVerifier` (HS256 verify: sig/iss/aud==this-server/exp), `mint_mcp_token(...)` — self-minted external-caller token (NOT the Supabase JWT).
- **mcp/server.py** — secured Streamable-HTTP MCP.
  - `build_mcp_server()` — FastMCP with the single `answer` tool; `McpSecurityMiddleware` — Host check -> Origin check -> token verify -> tenant on a contextvar (no passthrough); `mcp_allowed_origin_hosts(settings)`, `mcp_request_hosts(settings)`, `build_mcp_verifier(settings)`.

## guardrails/ , eval/
- **guardrails/router.py** — EMPTY (Day 6). **eval/router.py** — EMPTY (Day 7).

## app entrypoint
- **main.py** — `create_app()` — FastAPI factory: lifespan (app_user db pool, MCP session manager), installs the visitor gate, installs the owner body cap (guarded prefix derived from the tenants router, single source of truth), includes domain routers under `/v1`, mounts the secured MCP at `/mcp`.

## backend/scripts
- **apply_migrations.py** — apply `supabase/migrations/*.sql` as the owner (run before integration tests).
- **seed_local.py** — seed local widget keys + Supabase owner users.
- **e2e_doors.py** — the three-door end-to-end proof over real HTTP.
- **probe_vertex.py** — credential-gated, NEVER run in CI; reruns the ADR-0007 Vertex pre-flight on demand (model availability per location, embedding dim/norm); fails soft (exit 0) with no credential.

## supabase/migrations
- `0001_app_user.sql` (unprivileged role + grants), `0002_documents.sql`, `0003_chunks.sql` (pgvector + forced RLS + policy), `0004_widget_keys.sql` (public lookup + app_user SELECT).

## tests/ (mirrored tree)
- **unit/** — routing decisions, owner JWT verify + JWKS cooldown throttle, owner body cap, visitor gate, origins, MCP tokens + security middleware, secret guard, contexts, core adapters, three-door spine, Vertex model/location config (ADR-0007).
- **integration/** — tenant isolation sweep, `tenant_txn`, visitor gate over HTTP, owner body-cap wiring (real `create_app`), mounted MCP security, log hygiene, PDF extraction / DLQ / spike.
- **fixtures/pdf/** — `scanned`/`diagram`/`poison`/`encrypted.pdf` + `generate_fixtures.py`.

## docs/ and repo skills
- **docs/FOLLOWUPS.md** — accepted limitations and deferred hardening for working code; distinct from the stub ledger.
- **docs/build-reports/** — chronological factual build logs used as source material for build-in-public posts.
- **.claude/skills/build-report/SKILL.md** — running build-report skill; appends traceable facts, numbers, stub deltas, and do-not-post flags.

> Historical, kept as-is. Predates ADR-0006: this prompt names `get_current_tenant`, which was later removed in favor of per-door request contexts (spec amendment A1 → ADR-0006).

# Day 1 build prompt — the auth spine and the MCP spike

You are Claude Code, the implementer. This file is your instruction set for Day 1 of the `honest-agent` flagship. Read it whole before you write anything. Build exactly what it says, in the order it says, and stop where it tells you to stop.

The owner of this project reads this file too, so the plain-English explanations in brackets are for them. Keep them; do not delete them when you work.

## Before you touch any code, read these (they were freshly synced into the repo)

Read these four files in `./docs/` and treat them as the source of truth:

- `./docs/BUILD_SPEC_LOCKED.md` — the approved, locked spec. If anything in THIS prompt conflicts with it, the locked spec wins. Tell the owner about the conflict; do not silently pick one.
- `./docs/flagship_app_flow.md` — the end-to-end flow. Sections 2 (owner/setup), 3 (visitor/query), and 5 (MCP) are the ones Day 1 implements the front edge of.
- `./docs/step1_explained.md` — Day 1 in plain language, the same scope as this prompt.
- `./CLAUDE.md` (and its mirror `./AGENTS.md`) — the coding standards you must follow on every commit. These are load-bearing. The "HARD SELF-REVIEW" section at the bottom is part of your Definition of Done, expanded below.

If `./docs/` is missing any of these, stop and tell the owner before continuing.

## What already exists (Milestone 0 — do NOT rebuild it)

The repo is already primed. You are building ON TOP of this, not creating it:

- uv project, Python 3.12 pinned, committed `uv.lock`, `src/app` layout.
- Ruff (lint + format, strict select set including `ASYNC`, `S`, `B`), mypy strict with the Pydantic plugin, pytest with `asyncio_mode = "auto"`.
- A `core/` package: one typed `Settings(BaseSettings)`, structlog JSON logging bound to context, Logfire and Sentry stubs, an `AppError` hierarchy mapped centrally to RFC 9457 problem-details responses, and the single shared `get_current_tenant` dependency.
- Seven empty, wired domains: `tenants`, `ingestion`, `agent`, `retrieval`, `guardrails`, `eval`, `mcp`. The `agent` package already carries the Gemini-only provider interface and the typed honesty-verdict type.
- A three-layer test tree: `tests/unit`, `tests/integration`, `tests/eval` (eval isolated, its own CI job).
- GitHub Actions CI with a green quick-gate (ruff check, ruff format --check, mypy, unit tests), `uv sync --frozen`, actions pinned to commit SHAs.
- Local Supabase and Weaviate running via Docker, and a real gitignored `.env`.

Do not recreate the repo, the tooling, the CI skeleton, the `core/` package, or the domain folders. Day 1 fills in the auth spine and the MCP, using what is there.

## Day 1 scope, stated once, exactly

There are THREE request paths across TWO trust domains. Each path resolves its tenant (the owner whose data is in scope) from its OWN credential. They must never collapse into one. The whole point of Day 1 is to stand these three doors up, prove each one, and de-risk the MCP — the single scariest piece of the build — while there is still time to change course.

The three doors:

| Door | Who calls | Credential | Tenant resolved from | What is checked |
| --- | --- | --- | --- | --- |
| Owner / ingestion | the logged-in human site owner | a real Supabase login JWT [JSON Web Token, a small signed token proving who is logged in] | the JWT's `app_metadata` (NOT `user_metadata`) | signature (via Supabase JWKS), issuer, audience, expiry |
| Visitor / widget | a random visitor on the owner's site, NOT logged in | a PUBLIC widget key (sits in page source, not a secret) | the key maps to a tenant | key is known, request Origin/Referer on that key's allowed-domain list, rate limit, then sanitize to just the query |
| MCP / external caller | an external AI system (e.g. a customer's agent or ChatGPT) | an external-caller token (Day 1: a self-minted signed token), NOT the owner's Supabase JWT | the token's claims | signature, issuer, audience equal to THIS server, expiry, reject tokens not minted for this server, validate Origin, never pass the token upstream |

The core capabilities (`retrieve`, `answer`) are plain typed functions, exposed TWO ways via thin adapters: an in-process call for the widget gate, and an MCP tool for external callers. The honesty verdict is FUSED into `answer` (every call returns `{answer, verdict}`); it is never an optional tool. On Day 1 the core is a STUB returning typed placeholder shapes.

## Where the code goes (use the existing domains; do not invent new top-level structure)

- `tenants/` — owner-JWT verification, the three-path type contract, tenant resolution, and the widget-key store (Postgres). This domain owns "who is this caller and which tenant."
- A clear auth/gate module for the visitor widget middleware. Put it where it reads cleanly — either a `gate` submodule under `tenants/` or a small `auth` module under `core/` if it is cross-cutting. Use your judgment; keep it one obvious place, not scattered.
- `agent/` — the stub core (`retrieve`, `answer`-with-verdict) and the two thin adapters (in-process, MCP tool).
- `mcp/` — the remote Streamable-HTTP MCP server and its token + Origin checks.
- `retrieval/` — the `retrieve` stub can live here if that reads better than `agent/`; keep `answer` (which fuses the verdict) in `agent/`. Use judgment, keep it DRY, no duplication.

Tests sit beside the code in the mirrored `tests/` tree. The three-path unit tests are Day 1's CI artifact and go in `tests/unit`.

## How you work: autonomous, test-first, prove it with real runs, iterate until green

You run unattended. The owner will NOT babysit your output. Do not pause between steps to ask for permission or approval. Work through every step end to end, committing after each, fixing your own failures as you go. Only stop early for a genuine human-only blocker (see the bottom of this section).

**Test-first, every step.** For each step: write the test first, run it, watch it fail for the right reason, implement the code, run the test again, and do not move on until it passes and the quick-gate (`ruff check`, `ruff format --check`, `mypy src`, `pytest tests/unit`) is green.

**Prove the three doors with REAL end-to-end runs, not just unit tests.** Unit tests are necessary but not sufficient. After the steps are built, actually start the FastAPI app locally against the already-running local Supabase and Weaviate, and exercise all three doors over real HTTP, capturing the real output:
- **Owner door:** call the placeholder owner route with a genuine local Supabase token for a seeded test user (accept), and with a forged/expired/wrong-audience token and a `user_metadata`-only-tenant token (reject). Confirm the right tenant is resolved.
- **Visitor door:** POST a question to the widget endpoint with a seeded widget key from an allowed Origin (passes to the stub core), from a disallowed Origin (403), and with an unknown key (reject). Confirm the sanitized context carries only the query.
- **MCP door:** connect a REAL MCP client to `/mcp` (an MCP client library or the MCP inspector, not a hand-rolled fake), list the tools, and call the `answer` tool with a valid self-minted token and allowed Origin (success), then with a bad token and with a disallowed Origin (refused).

Write these end-to-end checks as RE-RUNNABLE scripts or integration tests (under `scripts/` or `tests/integration`), not one-off manual commands, so they can be run again on demand and in CI later. Capture their actual output for the report.

## Security acceptance tests you must write and run (negative/abuse cases — the doors only count if they REJECT)

A door that opens for the right caller is half a door. The other half is that it SLAMS on the wrong one. For each path, write these as real tests (unit where the check is pure, integration where it needs the live stack), watch them go red for the right reason against a stub, then make them pass. These are not optional; a missing negative test is a hole you have not proven closed. Do not just assert a 401/403 status — assert the request did NOT reach the core and NO tenant was resolved.

**Owner JWT (the one real login — get this exactly right or the whole spine is theatre).** Each of these tokens must be REJECTED, and you must confirm the rejection path resolves no tenant and runs no handler:
- `alg=none` token [an unsigned token claiming the server should trust it without a signature]. Reject.
- Algorithm-confusion: an RS256-style token re-signed as HS256 using the JWKS PUBLIC key bytes as the HMAC secret [the classic library-misuse bypass]. Reject. Your verifier must PIN the expected algorithm(s) from the JWKS, not accept whatever the token's header declares.
- Token with no `kid`, or a `kid` that matches no published key. Reject (do not fall back to "try every key" or "first key").
- Signature made with a wrong/attacker key. Reject.
- Expired token (`exp` in the past). Reject. Also a token with `nbf`/`iat` in the future. Reject (no "not yet valid" token slips through).
- Wrong issuer (`iss` not your Supabase issuer). Reject.
- Wrong audience (`aud` not your configured owner audience). Reject.
- Tenant claim present ONLY in `user_metadata` (and absent from `app_metadata`). Reject — never read tenant from `user_metadata`, even as a fallback. Also: a token whose `app_metadata` tenant differs from a `user_metadata` tenant must resolve the `app_metadata` one and ignore the other.
- No token / empty Authorization header / malformed (non-JWT) token / token with a tampered body. Reject each, with a clean problem-details error, no stack trace.

**Visitor widget gate.** Prove the gate, not just the happy path:
- Unknown widget key. Reject.
- Valid key but Origin spoofed to a domain NOT on that key's allowlist. 403. (And a different valid key's allowed Origin used against THIS key — still 403; the allowlist is per-key, not global.)
- Valid key with missing Origin AND missing Referer. Decide and TEST the decision explicitly (Day-1 default: reject when neither is present, since the gate cannot bind it). A present-but-empty Origin (`Origin: `) and `Origin: null` must NOT be treated as allowed.
- Referer-fallback abuse: a Referer pointing at an allowed host but an Origin pointing at a disallowed one — the disallowed Origin wins (reject). Do not let a forgeable Referer override a present Origin.
- Case/host confusion: `https://Allowed.com`, `https://allowed.com.evil.com`, `https://allowed.com:8443`, trailing-dot `allowed.com.`, and `allowed.com` vs `www.allowed.com` — match the host exactly per the allowlist; do not use naive `in`/`startswith`/`contains` substring checks. Test that `evil-allowed.com` and `allowed.com.evil.com` are REJECTED.
- Oversized body: a request body far over a sane cap is rejected BEFORE it is parsed or reaches the core (set and test a max-body limit; an unbounded body is a trivial DoS).
- Sanitization completeness: send a body with extra smuggled fields (a forged `tenant`/`tenant_id`, a `system`/`role` field, an injected `origin_override`, nested objects) and assert the `VisitorRequestContext` that reaches the core carries ONLY the query and the gate-resolved tenant — every smuggled field is dropped, and the client cannot influence the tenant. This is the mass-assignment / over-posting check.

**MCP external-caller token.** This is the scariest door; prove it refuses:
- Token whose `aud` is some OTHER server (not this one). Reject — accepting it is the confused-deputy / wrong-audience failure the spec forbids.
- Token whose `iss` is not your minting issuer. Reject.
- Expired token, and a replayed token past its `exp`. Reject.
- `alg=none` / wrong-signature MCP token (same discipline as the owner JWT — pin the algorithm, this is HMAC so reject any header claiming otherwise). Reject.
- Missing token / empty bearer. Reject.
- Origin present and on a disallowed host. 403 (the DNS-rebinding defense).
- No-passthrough proof: assert in a test that the inbound MCP token is NEVER read into, attached to, or forwarded on any outbound/upstream call the tool makes. The stub makes this easy to prove now; prove it now so it cannot regress. Confirm the MCP credential is genuinely a DIFFERENT secret/issuer/audience from the Supabase JWT path — a Supabase owner JWT presented to `/mcp` must be REJECTED (wrong issuer/audience), and an MCP token presented to the owner route must be REJECTED.

**Cross-cutting (these catch the leaks that sink a security review).**
- Secret non-leak: assert that no secret-bearing Settings field value (MCP signing secret, Supabase `service_role`, Vertex SA JSON) appears in ANY error/problem-details response body, log line, or browser-bound output. Trigger a failure on each door and grep the captured response + structured logs for those secret values — they must be absent.
- No internal disclosure: error responses are RFC 9457 problem-details with no stack trace, no file path, no library version, no raw exception string leaked to the client.
- Structured-log hygiene: tokens, widget keys, and Authorization headers are NOT recorded verbatim in structlog output (redact or omit). Assert a token value does not appear in the emitted logs for a request.
- Rate-limit seam exists: assert the `RateLimiter` interface is actually invoked on the visitor path (even though the stub always allows), so Day 11 swaps an implementation, not a missing call.
- Tenant-override impossibility: across ALL three paths, assert there is no request input (body field, header, query param) that can set or change the resolved tenant; tenant comes only from the verified credential. (Owner: `app_metadata`. Visitor: the key row. MCP: the token claim.)
- Dependency pinning respected: no new dependency added unpinned; `uv.lock` stays the source of truth; the quick-gate still runs `uv sync --frozen`.

Run the **security-review** skill on the day's diffs (see the hard self-review below). It must return PASS. These negative tests and that skill are aligned on purpose: the skill checks the same invariants these tests prove, so a passing skill and a passing negative-test suite should agree. If they disagree, you have a real gap — fix the code, not the test.

**Iterate-and-fix loop (this is the part that matters).** If anything is red — a unit test, an end-to-end script, `ruff`, `mypy`, or any of the three skill reviews (spec-review, senior-pass, security-review) — you FIX it yourself and re-run the whole gate. Repeat the loop until every test and every end-to-end script passes AND all three skill reviews return PASS. Do not report Day 1 done with anything red or any review item unaddressed. Re-running and fixing is expected, not a failure.

**When to stop and ask (only these).** Stop and tell the owner precisely, only if: a required real credential or secret cannot be self-provisioned locally (e.g. a cloud-only key), or something in this prompt genuinely conflicts with `./docs/BUILD_SPEC_LOCKED.md`. Everything else — failing tests, type errors, design choices within scope, flaky local setup — you resolve yourself.

## Build in this order. Commit after each step (Conventional Commits). One WHY per step.

### Step 1 — The three-path type contract, named in code before any handler
WHY: if the three entry shapes are not distinct types from the first line, they quietly collapse into one and the whole trust model rots.

Define three distinct, typed request-context shapes (Pydantic or dataclasses, your call, but typed end to end, no bare `Any`):
- `OwnerRequestContext` — carries the verified owner identity and the tenant resolved from `app_metadata`.
- `VisitorRequestContext` — carries the tenant resolved from the widget key, plus the sanitized query. No user identity.
- `ExternalCallerContext` — carries the tenant resolved from the external-caller token. Not an owner, not a visitor.

These are three separate types on purpose. Do not unify them behind one "AuthContext" that papers over the differences. Each path produces its own.
Commit: `feat(tenants): three-path request context types`

### Step 2 — Owner auth path (the only real login). Build fully.
WHY: this is the one true login; it gates ingestion, and getting JWT verification right is non-negotiable.

A FastAPI dependency that verifies a real Supabase login JWT:
- Fetch and cache Supabase's JWKS [JSON Web Key Set — the public keys Supabase publishes so you can check a token's signature]. Verify the signature against it. PIN the accepted algorithm(s) to what the JWKS keys actually are; never trust the algorithm named in the token's own header [trusting it is the alg=none and algorithm-confusion bypass]. Select the key by `kid`; if `kid` is missing or matches no published key, reject — do not fall back to trying every key. Cache the JWKS but make it rotatable: on a `kid` that is not in the cache, refetch the JWKS once (Supabase rotates its keys) before rejecting, and never fetch the JWKS on every request (that is a denial-of-service and SSRF footgun).
- Check issuer, audience, and expiry. Reject on any failure with the right problem-details error from the `AppError` hierarchy (do not invent a new error shape).
- Resolve the owner's tenant from the token's `app_metadata`, NOT `user_metadata`. (`user_metadata` is user-editable and is a known privilege-escalation vector; `app_metadata` is server-controlled.) If the tenant claim is missing, reject.
- This dependency gates the owner/ingestion routes. Wire it onto a placeholder owner route so it is exercisable; do NOT build ingestion (that is Days 3-4).

Tests: a valid token is accepted and resolves the right tenant; a token with a bad signature, wrong issuer, wrong audience, or expired is rejected; a token carrying the tenant only in `user_metadata` is rejected.
Commit: `feat(tenants): owner Supabase JWT auth dependency`

### Step 3 — Secret-on-server guard (do not call it "BFF" in owner-facing prose; explain it plainly). Mostly a guard + test.
WHY: any secret that reaches the browser bundle is shared with every attacker; one test makes that impossible to regress.

The browser must only ever hold the PUBLIC widget key. The model/service secrets (Vertex service-account JSON, Supabase `service_role` key, the MCP signing secret, etc.) live ONLY server-side, in `core/` Settings, and never reach a browser bundle. Settings already holds these typed; this step is the guard plus the test that proves it.
- Add a test that asserts the set of secret-bearing Settings fields is never referenced by any code path that produces browser-bound output, and that the only credential the visitor path hands back toward the browser is the public widget key. A pragmatic, real assertion is fine (e.g. enumerate the secret field names from Settings and assert none appear in any served-to-browser response model / bundle manifest you control today). Make it a guard that would actually fail if someone leaked a secret, not a comment.
Commit: `test(core): assert service secrets never reach the browser`

### Step 4 — Visitor widget-key gate as in-app FastAPI middleware (Option B, owner-decided; NOT a Cloudflare Worker). Build (a),(b),(d) fully; STUB (c).
WHY: visitors have no login, so the public key plus Origin binding plus rate limit plus narrow scope is the entire visitor trust boundary, and it must be a first-class, tested piece.

This is in-app FastAPI middleware [code that runs on every matching request before the handler]. The owner decided Option B (in-app), not a Cloudflare Worker, signed off 2026-06-30. A request carrying a public widget key must pass, in this order:
- (a) **Key exists** in the valid-keys store (Postgres — see KEY STORAGE below). Build fully.
- (b) **Origin/Referer allowlist**: the request's Origin (or Referer) must be on THAT key's list of allowed domains. 403 if present and not allowed. Build it SIMPLY, but simple does NOT mean sloppy: match the host EXACTLY (a full-host compare, never a `startswith`/substring/`contains` check, or `allowed.com.evil.com` and `allowed.com.attacker.net` slip through; handle a trailing dot, an explicit port, and `Origin: null`). It is a deterrent [a non-browser client can spoof the header], not the load-bearing defense, so do not add elaborate logic beyond a correct exact-host match.
- **Body-size cap** belongs here: reject an over-large request body BEFORE parsing it, so an anonymous visitor cannot exhaust memory even with the rate limiter stubbed. This cap lives in the gate.
- (c) **Per-key and per-IP rate limit**: STUB this behind a clean, typed interface (e.g. a `RateLimiter` protocol with a no-op or always-allow implementation). The real limiter is Day 11. The interface must be real and swappable; the implementation is a stub.
- (d) **Sanitize** the request down to just the query, then call the core IN-PROCESS via the thin adapter. Build fully. The gate calls the core directly in-process; it NEVER routes the visitor request through the MCP (no self-network-hop).

The load-bearing controls here are the narrow scope (tenant-grounded answers only, capped output — enforced later) and the rate limit (Day 11), not the Origin check. Build accordingly: simple Origin check, clean rate-limit seam.

Tests: an allowed key from an allowed Origin passes and reaches the (stub) core; an allowed key from a disallowed Origin gets 403; an unknown key is rejected; the sanitized context carries only the query.
Commit: `feat(tenants): visitor widget-key gate middleware`

### Step 5 — Core capabilities as plain functions + two thin adapters. STUBS.
WHY: one core exposed two ways with no duplication is the architecture the whole rest of the build leans on; defining it now (stubbed) sets the seam correctly.

- `retrieve(tenant, query)` and `answer(tenant, query) -> {answer, verdict}` as plain, typed functions. The honesty verdict is FUSED into `answer` — every call returns the verdict alongside the answer; it is never a separate optional tool. On Day 1 both return typed placeholder shapes (real retrieval is Day 5, real grounding/refusal is Day 6). Use the existing typed honesty-verdict type from `agent/`; do not invent a parallel one.
- Two thin adapters over the ONE core: the in-process adapter the widget gate calls (Step 4), and the MCP tool adapter (Step 6). No business logic in the adapters — they translate the edge into a core call and back. DRY: no copy of the core logic in either adapter.

Tests: each adapter calls the same core and returns the typed `{answer, verdict}` shape.
Commit: `feat(agent): stub core capabilities and two thin adapters`

### Step 6 — The MCP spike (the main event). Build the ONE correct check end to end.
WHY: MCP auth is the single biggest schedule risk in the project; a working secured remote door proven on Day 1 is what stops a late-week surprise from sinking the flagship.

Stand up a remote Streamable-HTTP MCP server [Model Context Protocol — the standard way external AI tools call tools on your server; Streamable-HTTP — the modern transport that runs as a normal web service reachable over the internet] at `/mcp` on the SAME Python service. Secure it as an OAuth 2.1 Resource Server [a server that only validates inbound tokens and serves the tool; it does not itself issue tokens]. Demonstrate ONE correct check, end to end:
- Pull the inbound bearer token. Validate its **signature**, **issuer**, **audience equal to this server** (per RFC 8707), and **expiry**.
- **Reject any token not minted for this server** (wrong audience, wrong issuer).
- **Validate the Origin header**: 403 when Origin is present and not allowed (this is the DNS-rebinding defense).
- **Never pass the inbound token upstream** to anything.

The Day-1 token is a SELF-MINTED signed token: the server signs it with a signing secret stored in `.env` (in `core/` Settings), and verifies it by that signature + issuer + audience + expiry. This is EXPLICITLY NOT the owner's Supabase JWT — it is a different credential for a different trust domain. (Using the owner's Supabase JWT here would be the "token passthrough / wrong audience" error the MCP security spec forbids.)

**Do NOT over-build this.** "OAuth 2.1 Resource Server" here means the validation DISCIPLINE (check signature, issuer, audience, expiry; reject what is not for you), not a full OAuth stack. On Day 1 the same service both mints and verifies the token with a shared signing secret, so do NOT pull in a third-party OAuth/identity library, do NOT stand up an authorization server, a discovery document, a JWKS endpoint for the MCP, dynamic client registration, or PKCE. Those are the Day-12/production write-up, named as a comment only. A self-signed token plus the four checks plus the Origin check is the whole Day-1 job. This step is exactly where over-building is the risk Day 1 exists to contain, so keep it minimal.

Expose the `answer` capability (returning `{answer, verdict}`) as the SINGLE MCP tool, via the thin adapter over the stub core from Step 5.

Confirm an MCP client (e.g. Claude Code itself) can LIST and CALL the tool through the secured endpoint with a valid token and allowed Origin, and is refused with a bad token or a disallowed Origin. Capture that proof for the report.
Commit: `feat(mcp): secured Streamable-HTTP server with external-caller token check`

### Step 7 — CI: add the three-path unit tests to the green quick-gate. Keep it green.
WHY: the spine is only real if it is enforced on every push; the quick-gate must guard all three doors from Day 1.

Add unit tests for all three paths to the already-green quick-gate:
- Owner: JWT accept / reject (bad sig, bad issuer, bad audience, expired, `user_metadata`-only tenant).
- Widget: Origin accept / reject, unknown-key reject, sanitized-context shape.
- MCP: token accept / reject (wrong audience, expired), Origin 403.

Run the full quick-gate locally (`ruff check`, `ruff format --check`, `mypy src`, `pytest tests/unit`) and keep `main` green.
Commit: `test: three-path auth unit tests in the quick-gate`

## KEY STORAGE (build it this way, exactly)

- **Widget keys are PUBLIC identifiers.** Store them in Postgres (Supabase), each row linking the key to its tenant and to its list of allowed origins. Do NOT hash them — their safety comes from origin-binding + rate limit + narrow scope, not from secrecy. **Seed widget keys for the two demo tenants** so the gate is testable end to end.
- **The MCP external-caller credential on Day 1 is the single signing secret in `.env`.** The server mints and verifies its own signed tokens with it. The production path — a hashed-keys table in Postgres (key hashed, linked to tenant + scope + expiry) so multiple AI clients can each have their own credential — is written up as a code comment near the MCP token-verification code AND/OR a short README note. It is NOT built on Day 1.

## Local config and env you must wire (or the accept-path tests cannot pass)

The token checks need concrete values to validate against. Wire these through `core/` Settings and the local `.env`, do not hard-code them in logic:
- The Supabase **issuer** and **audience** to validate owner JWTs against (read them from your running local Supabase).
- The **MCP signing secret**, and the **issuer** and **audience** literals your self-minted MCP tokens carry and are checked against.

Before the end-to-end runs, make sure the local `.env` actually holds these and that a seeded local Supabase test user exists, so the accept-path tests run against the real local stack, not mocks. If a value is genuinely cloud-only and cannot be set locally, stop and tell the owner exactly which one. Otherwise set sensible local values, write them into the gitignored `.env`, and note them in the report.

## Standards you enforce on every commit (from the locked spec and CLAUDE.md)

Typed Python end to end, no bare `Any`. Clean conventional, domain-first architecture. DRY and reusable. Real error handling through the `AppError` hierarchy mapped to RFC 9457 — no bare `except`, no catch-and-return-200, no silent `pass`. No dead code, no commented-out code. Minimal comments: only a non-obvious WHY (a workaround, a business rule, an ordering constraint), never narration. Tests beside the code, all green in CI. Conventional Commits. No UI. Local only, no deploy. Never block the event loop (`async def` for awaitable I/O). Nothing built ahead of its day.

## Do NOT build these on Day 1 (deferred on purpose — building them now is a mistake)

- Real retrieval — Day 5.
- Real grounded answer and real honesty verdict logic — Day 6 (Day 1 returns typed stubs).
- The real rate limiter — Day 11 (Day 1 stubs it behind a clean interface).
- The full OAuth 2.1 authorization-server flow and the Protected Resource Metadata document (RFC 9728) — Day 12 (Day 1 demonstrates ONE check: audience/issuer/signature/expiry on a self-minted token).
- The standalone general-purpose evaluator tool — later (keep it distinct from the fused verdict).
- Ingestion — Days 3-4.
- The tenant-isolation proof test — Day 2.
- The dashboard and the widget UI — Days 9-10.
- Deployment — Day 9.

If you find yourself reaching for any of these to make Day 1 "feel complete," stop. Day 1 is the spine, stubbed core, secured MCP. Nothing more.

## Definition of done for Day 1

Day 1 is done when ALL of these are true:

1. The three-path type contract exists: `OwnerRequestContext`, `VisitorRequestContext`, `ExternalCallerContext` are distinct typed shapes, each resolving its tenant from its own credential.
2. Owner path: a real Supabase JWT is verified (signature via JWKS, issuer, audience, expiry) and the tenant is resolved from `app_metadata`; it gates a placeholder owner route. Accept/reject tested.
3. Secret-on-server guard: a test asserts service/model secrets live only server-side and never reach a browser bundle.
4. Visitor widget-key gate runs as in-app FastAPI middleware: key-exists (a) and Origin allowlist (b) and sanitize-to-query (d) built fully; rate limit (c) stubbed behind a clean typed interface. The gate calls the core in-process, never through the MCP. Accept/reject/unknown-key tested.
5. Core `retrieve` and `answer`-with-verdict exist as typed stub functions, with the verdict FUSED into `answer`, exposed via two thin adapters (in-process + MCP tool) over the ONE core.
6. MCP: a remote Streamable-HTTP server at `/mcp` on the same service validates a self-minted external-caller token (signature, issuer, audience == this server, expiry), rejects tokens not minted for this server, returns 403 on a present-and-invalid Origin, and never passes the token upstream. An MCP client can list and call the single `answer` tool through it. Bad token and bad Origin are refused. This is NOT the owner's Supabase JWT.
7. Widget keys are seeded in Postgres for the two demo tenants (public, not hashed, linked to tenant + allowed origins). The hashed-keys production path is written up as a comment/README note, not built.
8. CI quick-gate is GREEN with the three-path unit tests added.
9. Real end-to-end runs PASS: re-runnable scripts or integration tests start the app against the local stack and exercise all three doors over real HTTP (owner accept/reject, visitor pass/403/unknown-key, MCP list-and-call success plus bad-token and bad-Origin refusal), and all are green.
10. All three skill reviews (spec-review, senior-pass, security-review) returned PASS after your fixes.
11. Nothing from the "Do NOT build" list was built.

## Before you declare Day 1 done — the hard self-review (do not skip)

Run these THREE skills on the day's diffs and FIX every BLOCKED / CHANGES-REQUIRED item before you report done. All three live in `./.claude/skills/`:

1. **spec-review** — does the work match `./docs/BUILD_SPEC_LOCKED.md` and the Day-1 scope above? Anything built ahead of its day, anything missing, anything that contradicts the locked spec?
2. **senior-pass** — clean architecture, DRY, typed end to end, tested, no comment rot, real error handling, nothing mediocre.
3. **security-review** — the three doors hold: owner JWT verification is real and complete; the secret-on-server guard actually guards; the widget gate's Origin/key checks are correct; the MCP token check (signature/issuer/audience/expiry, reject wrong-audience, Origin 403, no passthrough) is correct and the self-minted token is genuinely separate from the Supabase JWT.

Work is NOT finished until all three pass. If any flags something, fix it and re-run. No exceptions under deadline.

## Then report (and stop — do NOT start Day 2)

Give the owner a concise report:
- What was built (the three doors, the stub core + adapters, the secured MCP).
- What is stubbed and why (the core capabilities, the rate limiter) and which day makes each real.
- What was deferred and why (the "Do NOT build" list).
- The green quick-gate output (the actual command output).
- The end-to-end run output for all three doors (the actual output from the re-runnable scripts/integration tests), and where those scripts live so they can be run again.
- The result of each of the three skill reviews (spec-review, senior-pass, security-review) — pass, or what was flagged and how you fixed it across the iterate loop.
- The MCP proof: that a real client listed and called the tool through the secured endpoint, and that a bad token and bad Origin were refused.

Then STOP. Do not start Day 2 (tenant isolation). That is a separate day with its own non-negotiable artifact.

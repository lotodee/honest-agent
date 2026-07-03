---
name: security-review
description: A blunt application-security review on any change before it is considered done. Use this after every implementation, before declaring work done, before staging or committing, and before opening a PR, and ALWAYS on any change that touches authentication, authorization, multi-tenant isolation, secrets or env, input handling, the MCP or any external/outbound call, error handling, or logging. It runs diff-driven over the real changed files, checks both conventional (OWASP) and non-conventional loopholes against this project's locked invariants, rates findings by severity, and BLOCKS until Critical and High findings are fixed. Run it whenever someone says a change is done or ready, or asks for a security review.
---

# Security Review

You are a principal application-security engineer doing the last review before this code is allowed to be called done. Be blunt. You do not soften findings. "It works and nothing obviously broke" does not pass. A security hole that has not been exercised is still a hole. You give a clear verdict, a severity-ranked list of findings with file, line, the concrete exploit, and the exact fix, and you BLOCK until the Critical and High items are fixed.

## This project's invariants (judge every change against these)

These are LOCKED. A change that breaks any of them is at least High, usually Critical.

- Three request paths across two trust domains, each resolving its tenant from its OWN credential, never collapsed: owner Supabase JWT (the only login), visitor public widget key + Origin allowlist (no login), MCP external-caller token (Day 1: self-minted signed token).
- Tenant id comes ONLY from the verified credential. Owner: from `app_metadata`, never `user_metadata`. Visitor: from the widget-key row. MCP: from the token claim. No request input (body, header, query) may set or change the tenant.
- Postgres RLS is FORCED. App DB role is non-owner and non-BYPASSRLS. Writes carry WITH CHECK. No code path reads or writes across tenants.
- Secrets (MCP signing secret, Supabase `service_role`, Vertex service-account JSON) live ONLY server-side in `core/` Settings/env. Never in browser-bound output, never logged, never in an error body. The browser holds only the PUBLIC widget key.
- The MCP self-minted token is a DIFFERENT credential from the Supabase JWT (different secret, issuer, audience). No token passthrough: an inbound MCP token is never forwarded upstream. Audience must equal this server; reject tokens not minted for it.
- LLM, vision, embeddings: Gemini via Vertex AI ONLY. No other live model provider in generation, vision, or embedding paths.
- Errors surface as RFC 9457 problem-details. No stack traces or internals to clients.

## Step 0 - Read the change properly, then run the tools

Do not review from memory and do not guess. Ground every finding in the real change and, where possible, real tool output.

1. `git diff` (or `git diff --staged`) to find exactly what changed. Read each modified file END TO END, not only the hunks, plus the security-relevant code around it (the dependency that calls this, the handler this guards, the Settings field this reads).
2. For anything touching auth, tenancy, secrets, input, the MCP, or external calls, trace the full path: where does the credential come from, where is the tenant set, where does untrusted input enter, where does a secret live, what goes out over the wire.
3. Run what you can: the test suite (especially the negative/abuse tests), the type checker, and the linter (the security lint set). A finding backed by a failing or missing test is stronger than an assertion. If a negative test that SHOULD exist is missing, that absence is itself a finding.

## The checklist you always run

Run every section. For each item, decide PASS or a finding with severity, file+line, exploit/impact, and the exact fix.

### 1. Authentication - token validation done right
- Signature verified against the correct key. Algorithm PINNED to the expected one(s); the token's own `alg` header is NOT trusted. No `alg=none` accepted. No algorithm-confusion (an RS256 token verified as HS256 with the public key as the HMAC secret must be rejected).
- `iss` checked against the configured issuer. `aud` checked and equal to this server (for the MCP, per RFC 8707). `exp` enforced; `nbf`/`iat` not in the future.
- `kid` used to select the key; missing/unknown `kid` rejected, with no "try every key" or "use the first key" fallback.
- JWKS cached AND rotatable (a key roll does not require a redeploy; a cache miss refetches). No unbounded fetch-per-request (SSRF/DoS) and no never-refresh.
- Missing, empty, and malformed tokens are rejected cleanly. Rejection resolves NO tenant and runs NO handler.

### 2. Authorization and MULTI-TENANT ISOLATION
- Every data access is scoped to the caller's tenant. There is no query, retrieval, or write that can reach another tenant's data.
- Tenant id comes from the verified credential ONLY (owner `app_metadata`, visitor key row, MCP token claim). Confirm NO request input can set or override it (this is also the mass-assignment check: search the request model for a tenant/tenant_id field bound from the body).
- Postgres RLS is forced; the app role cannot bypass it; writes use WITH CHECK so a row cannot be inserted under another tenant. Weaviate access is shard/tenant-scoped.
- No IDOR: an id taken from the request is always re-scoped to the caller's tenant before use, never trusted as already-authorized.

### 3. Input validation and injection
- SQL/NoSQL: parameterized queries only; no string-built SQL; no untrusted input in a Weaviate filter/GraphQL string.
- Command and path: no shell built from input; no path traversal on any file/object key derived from input.
- SSRF: any OUTBOUND fetch (site crawl, JWKS, object storage, webhook, MCP-driven call) validates and pins the destination; no user-controlled URL is fetched without an allowlist; no fetch to internal/metadata addresses.
- Prompt injection / tool abuse on LLM and agent surfaces: retrieved/document content is delimited/spotlighted and treated as data, not instructions; the model cannot be steered to exceed its tenant scope or call a tool it should not; tool surface is minimal and scoped.
- Deserialization: no `pickle`/`eval`/unsafe YAML on untrusted bytes. Request bodies are size-capped before parsing.

### 4. Secrets management
- No secret in browser-bound output or the client bundle. No secret logged. No secret in an error/problem-details body or exception message returned to a client. No secret committed (scan the diff for added keys, tokens, service-account JSON, connection strings).
- Secrets read only from `core/` Settings/env, never hard-coded in logic. The secret-on-server guard still holds.

### 5. Transport, headers, CORS, Origin
- TLS assumed in prod. CORS reflects a validated Origin when credentials are needed, never blind wildcard with credentials. Origin/Referer checks match the host EXACTLY (no substring/`startswith` match; `allowed.com.evil.com`, trailing dot, port confusion, `Origin: null`, and empty Origin are all handled). Security headers present where relevant.

### 6. MCP and agent-specific risk
- No token passthrough: the inbound MCP token is never read into or attached to any upstream/outbound call. Audience binding enforced (token minted for this server only). No confused-deputy: the server does not use its own privileged credential to act on an unverified caller's behalf. Tool scope is narrow; no over-broad capability exposed.

### 7. Error handling and information disclosure
- Failures go through the `AppError` hierarchy to RFC 9457 problem-details. No stack trace, file path, library version, raw exception string, or internal identifier leaks to the client. Errors that should surface, surface; none are swallowed into a broken-but-200 state.

### 8. Abuse and rate limiting
- A real rate-limit seam exists and is actually invoked on the public/visitor path (even if the implementation is a stub). Body-size and obvious-abuse caps are present. No unbounded loop or fetch reachable by an anonymous caller.

### 9. Dependency and supply chain
- New deps are pinned; the lockfile is the source of truth and the gate runs a frozen sync. No known-vuln pattern introduced. No `curl | bash`, no unpinned GitHub Action (actions pinned to a commit SHA), no fetch-and-execute of remote code.

### 10. Logging and PII
- Structured logs do NOT record tokens, widget keys, Authorization headers, secrets, or unnecessary PII verbatim (redact or omit). Logs are enough to debug, not enough to replay an auth.

### 11. Non-conventional loopholes - think like an attacker about THIS change
Push past the checklist. For the specific code in the diff, ask:
- Auth-bypass via ORDERING: is a check done after the side effect it was meant to guard? Can the handler run before the gate? Is there a route that skips the middleware?
- Race conditions / TOCTOU: is something validated and then re-fetched/re-used such that it can change in between (a key revoked between check and use, a tenant swapped)?
- Mass assignment / over-posting: can a client set a field it should not (tenant, role, is_admin, origin override) by adding it to the body?
- IDOR and enumeration: are ids re-scoped to the tenant? Do error messages or timing reveal whether a key/tenant exists?
- Cache poisoning / header smuggling: can a forged or duplicated header (X-Forwarded-*, Origin, Host) change a security decision or get cached and served to others?
- Anything in this change that a determined attacker would reach for first. Name it even if the checklist did not.

## Step - Verdict

Severity-rank every finding: **Critical** (direct auth bypass, cross-tenant read/write, secret leak, RCE/SSRF to internal), **High** (exploitable with modest effort, or breaks a locked invariant), **Medium** (defense-in-depth gap, hardening, weak error hygiene), **Low** (minor/cosmetic). For each finding give: file and line, the concrete exploit and its impact, and the exact fix.

**PASS** only if there are NO Critical and NO High findings, and every Medium is either fixed or has a written, justified reason to defer. State briefly what you confirmed holds (the invariants above).

**BLOCKED** if any Critical or High finding exists (or an unjustified Medium). Give the prioritized list, Critical first, then High, then Medium, then Low. State plainly: this change does NOT ship until the Critical and High findings are fixed. After fixes, RE-RUN the full checklist from Step 0 before changing the verdict: a fix can open a new hole.

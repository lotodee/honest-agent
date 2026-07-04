# Follow-ups — deferred hardening & accepted limitations

A register of known limitations on **working** code: hardening we chose to defer, and
limitations we accept as safe today under a stated condition. It exists so these live
somewhere searchable, not only in a docstring a reviewer has to stumble on.

**This is not the stub ledger.** A *stub* is an unimplemented placeholder with a close
condition — those go in [`STUB_LEDGER.md`](STUB_LEDGER.md). The items here are real,
finished code with a documented edge or a bounded trade-off.

Each item records: **what**, **where**, **status** (deferred hardening vs accepted),
**why** it was deferred or is safe to accept, and the **trigger** to revisit.

---

## 1. Visitor gate buffers the full body before the size check (no/chunked Content-Length)

- **What:** For a request with no `Content-Length` (e.g. `Transfer-Encoding: chunked`),
  the declared-length precheck is skipped, and `await request.body()` reads the entire
  body into memory before `VisitorGate.authorize` applies the real-bytes cap
  (`len(body) > max_body_bytes`). So an oversized chunked body is fully buffered before
  it is rejected.
- **Where:** [`backend/src/app/tenants/gate.py`](../backend/src/app/tenants/gate.py) —
  `visitor_gate_middleware` (`body = await request.body()`) and `VisitorGate.authorize`
  (`len(body)` check).
- **Status:** Deferred hardening (fix later). **Pre-existing** — predates the
  Content-Length parsing fix.
- **Why deferred:** The common oversized case (an honest client sending a real
  `Content-Length`) is already rejected cheaply before any body read. Closing the
  chunked path needs a streaming read that aborts mid-body, which is more machinery than
  the current single-container, low-traffic posture warrants.
- **Trigger to revisit:** Hardening the visitor door for hostile traffic (Day 11), or
  putting the documented Cloudflare/WAF front in place. **Fix:** stream-and-abort (read
  in bounded chunks, abort once the cap is exceeded) or a server-/proxy-level body limit.

## 2. Owner body cap is declared-`Content-Length` only

- **What:** The owner-door body cap rejects on the declared `Content-Length` header and
  does **not** measure the actual bytes received, so a chunked or absent-length body
  bypasses it entirely.
- **Where:** [`backend/src/app/tenants/owner_gate.py`](../backend/src/app/tenants/owner_gate.py).
- **Status:** Accepted.
- **Why safe today:** The only owner route is `GET /v1/tenants/me`, which reads no body.
  The cap is defense-in-depth on a surface that carries no body to abuse. Measuring the
  body here (buffering it purely to size it) would reintroduce the very memory-DoS the
  header check avoids.
- **Trigger to revisit:** Any future owner route that **parses a request body** must
  enforce the real-bytes cap on what it actually read (as `VisitorGate.authorize` does)
  and must not rely on this middleware alone.

## 3. JWKS refetch throttle is per-process

- **What:** The owner-door JWKS refetch throttle (one fetch per cooldown) is enforced in
  a per-process in-memory resolver. With N worker processes the outbound-fetch bound is
  **N per cooldown**, not 1.
- **Where:** [`backend/src/app/tenants/owner_auth.py`](../backend/src/app/tenants/owner_auth.py)
  — `JwksKeyResolver`, held by a per-process `lru_cache` singleton.
- **Status:** Accepted (inherent to a shared-nothing multi-process deployment).
- **Why accepted:** N × once-per-cooldown (default 300s) is still a tiny, bounded rate
  against Supabase's JWKS endpoint — the amplification the throttle targets (one fetch
  per request) is gone. A cross-process shared throttle would need shared state
  (Redis/DB) that is not warranted at the current worker count and scale.
- **Trigger to revisit:** Worker count grows large, or Supabase imposes a JWKS rate
  limit a few-per-cooldown burst could trip. **Fix:** move the throttle + negative cache
  to shared state.

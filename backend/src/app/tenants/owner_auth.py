"""Owner door: verify a real Supabase login JWT and resolve the tenant.

The accepted algorithm is PINNED to ES256 (what the Supabase JWKS publishes); the
token's own `alg` header is never trusted, which closes the alg=none and the
RS256-as-HS256 confusion bypasses. The tenant is read ONLY from `app_metadata`
(server-controlled), never `user_metadata` (user-editable, a privilege-escalation
vector). A rejection resolves no tenant and runs no handler.
"""

import asyncio
import threading
import time
from collections.abc import Callable
from functools import lru_cache

import httpx
import jwt
from fastapi import Request
from jwt import PyJWK

from app.core.bearer import parse_bearer
from app.core.errors import AuthenticationError, ServiceUnavailableError
from app.core.settings import Settings, get_settings
from app.tenants.contexts import OwnerRequestContext

JwksFetcher = Callable[[], list[dict[str, object]]]

_ALGORITHMS = ("ES256",)
_CLOCK_SKEW_LEEWAY_SECONDS = 10
_JWKS_FETCH_TIMEOUT_SECONDS = 5.0
_JWKS_REFRESH_COOLDOWN_SECONDS = 300.0
# Cap the negative cache so a flood of distinct random kids cannot grow it without
# bound; the cooldown throttle already bounds outbound fetches, this just bounds memory.
_NEGATIVE_CACHE_MAX_ENTRIES = 1024


class JwksKeyResolver:
    """Resolve a signing key by `kid`, caching the JWKS and refetching on a miss so a
    Supabase key rotation does not need a redeploy.

    Refetches are THROTTLED to at most one per `cooldown_seconds`. Without this, an
    anonymous caller sending tokens bearing random `kid`s (read from the *unverified*
    header) would force one outbound JWKS fetch per request, saturating the threadpool
    and flooding the JWKS endpoint. An unknown `kid` seen within the cooldown is
    remembered in a small bounded negative cache so repeats reject with no work, and a
    throttled miss rejects without fetching. A genuinely rotated `kid` is still picked
    up on the first miss after the cooldown.

    It never fetches per request and never falls back to trying every key on a miss.
    """

    def __init__(
        self,
        fetch: JwksFetcher,
        *,
        cooldown_seconds: float = _JWKS_REFRESH_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._keys: dict[str, PyJWK] = {}
        # The resolver is a shared singleton driven from asyncio.to_thread worker
        # threads, so the miss path (which mutates _unknown_kids/_last_refresh and may
        # fetch) must be serialized. A threading.Lock, not asyncio: it runs in threads.
        self._lock = threading.Lock()
        self._cooldown = cooldown_seconds
        # monotonic clock: a wall-clock adjustment must not widen or collapse the
        # cooldown window. -inf so the first miss always refreshes.
        self._clock = clock
        self._last_refresh = float("-inf")
        self._unknown_kids: dict[str, float] = {}

    def get(self, kid: str) -> PyJWK:
        # Fast path stays lock-free: a single dict read. _refresh only ever REBINDS
        # _keys wholesale (never mutates it in place), so a concurrent refresh is a
        # clean reference swap, not a torn read.
        key = self._keys.get(kid)
        if key is not None:
            return key
        # Miss path: serialize it. It mutates shared state and may fetch, and runs in
        # worker threads; unguarded, a concurrent prune could raise "dict changed size
        # during iteration" (a 500) and two threads could double-fetch at the boundary.
        with self._lock:
            # Re-check under the lock: another thread may have refreshed _keys while we
            # waited, so a just-rotated kid can now be present.
            key = self._keys.get(kid)
            if key is not None:
                return key
            now = self._clock()
            seen_at = self._unknown_kids.get(kid)
            if seen_at is not None and now - seen_at < self._cooldown:
                raise AuthenticationError("unknown token signing key")
            if now - self._last_refresh >= self._cooldown:
                self._refresh(now)
                rotated = self._keys.get(kid)
                if rotated is not None:
                    return rotated
            self._remember_unknown(kid, now)
            raise AuthenticationError("unknown token signing key")

    def _refresh(self, now: float) -> None:
        # Record the attempt BEFORE fetching, so a failing/hanging JWKS endpoint is
        # throttled too and cannot itself become the amplification vector.
        self._last_refresh = now
        try:
            keys: dict[str, PyJWK] = {}
            for entry in self._fetch():
                kid = entry.get("kid")
                if isinstance(kid, str) and kid:
                    keys[kid] = PyJWK.from_dict(entry)
        except Exception as exc:
            # A JWKS endpoint that is down, hanging, returning an error, or serving a
            # malformed key is an UPSTREAM failure, not a bad token. Convert it to a
            # clean, retryable 503 (rendered by the RFC 9457 handler) instead of
            # letting a raw httpx/jwt exception fall through to a generic 500. This
            # still fails closed — no token is accepted — and the refetch is already
            # throttled to once per cooldown by the _last_refresh stamp above.
            raise ServiceUnavailableError(
                "token signing keys are temporarily unavailable"
            ) from exc
        self._keys = keys
        # Fresh JWKS may contain a kid we just rejected; drop stale negatives so a
        # rotated key is never shadowed by an earlier miss.
        self._unknown_kids.clear()

    def _remember_unknown(self, kid: str, now: float) -> None:
        if len(self._unknown_kids) >= _NEGATIVE_CACHE_MAX_ENTRIES:
            cutoff = now - self._cooldown
            self._unknown_kids = {
                k: seen for k, seen in self._unknown_kids.items() if seen >= cutoff
            }
            if len(self._unknown_kids) >= _NEGATIVE_CACHE_MAX_ENTRIES:
                self._unknown_kids.clear()
        self._unknown_kids[kid] = now


class OwnerTokenVerifier:
    def __init__(
        self, *, resolver: JwksKeyResolver, issuer: str, audience: str
    ) -> None:
        self._resolver = resolver
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> OwnerRequestContext:
        key = self._resolver.get(self._key_id(token))
        claims = self._decode(token, key)
        self._reject_future_iat(claims)
        return OwnerRequestContext(
            tenant_id=self._tenant_id(claims),
            user_id=self._user_id(claims),
        )

    def _key_id(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("malformed token") from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthenticationError("token missing key id")
        return kid

    def _decode(self, token: str, key: PyJWK) -> dict[str, object]:
        try:
            return jwt.decode(
                token,
                key.key,
                algorithms=list(_ALGORITHMS),
                issuer=self._issuer,
                audience=self._audience,
                leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("token verification failed") from exc

    def _reject_future_iat(self, claims: dict[str, object]) -> None:
        issued_at = claims.get("iat")
        if (
            isinstance(issued_at, int | float)
            and issued_at > time.time() + _CLOCK_SKEW_LEEWAY_SECONDS
        ):
            raise AuthenticationError("token issued in the future")

    def _tenant_id(self, claims: dict[str, object]) -> str:
        app_metadata = claims.get("app_metadata")
        if isinstance(app_metadata, dict):
            tenant_id = app_metadata.get("tenant_id")
            if isinstance(tenant_id, str) and tenant_id:
                return tenant_id
        raise AuthenticationError("token has no tenant in app_metadata")

    def _user_id(self, claims: dict[str, object]) -> str:
        subject = claims.get("sub")
        if isinstance(subject, str) and subject:
            return subject
        raise AuthenticationError("token missing subject")


def _jwks_fetch(jwks_url: str) -> JwksFetcher:
    def fetch() -> list[dict[str, object]]:
        response = httpx.get(jwks_url, timeout=_JWKS_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        keys = payload.get("keys", []) if isinstance(payload, dict) else []
        return [entry for entry in keys if isinstance(entry, dict)]

    return fetch


def build_owner_verifier(settings: Settings) -> OwnerTokenVerifier:
    return OwnerTokenVerifier(
        resolver=JwksKeyResolver(
            _jwks_fetch(settings.supabase_jwks_url),
            cooldown_seconds=settings.owner_jwks_refresh_cooldown_seconds,
        ),
        issuer=settings.supabase_jwt_issuer,
        audience=settings.supabase_jwt_audience,
    )


@lru_cache(maxsize=1)
def _live_verifier() -> OwnerTokenVerifier:
    return build_owner_verifier(get_settings())


def bearer_token(request: Request) -> str:
    return parse_bearer(request.headers.get("Authorization"))


async def get_owner_context(request: Request) -> OwnerRequestContext:
    token = bearer_token(request)
    verifier = _live_verifier()
    # verify can do a one-off blocking JWKS fetch on a cache miss; keep it off
    # the event loop.
    return await asyncio.to_thread(verifier.verify, token)

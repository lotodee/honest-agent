"""Owner door: verify a real Supabase login JWT and resolve the tenant.

The accepted algorithm is PINNED to ES256 (what the Supabase JWKS publishes); the
token's own `alg` header is never trusted, which closes the alg=none and the
RS256-as-HS256 confusion bypasses. The tenant is read ONLY from `app_metadata`
(server-controlled), never `user_metadata` (user-editable, a privilege-escalation
vector). A rejection resolves no tenant and runs no handler.
"""

import asyncio
import time
from collections.abc import Callable
from functools import lru_cache

import httpx
import jwt
from fastapi import Request
from jwt import PyJWK

from app.core.bearer import parse_bearer
from app.core.errors import AuthenticationError
from app.core.settings import Settings, get_settings
from app.tenants.contexts import OwnerRequestContext

JwksFetcher = Callable[[], list[dict[str, object]]]

_ALGORITHMS = ("ES256",)
_CLOCK_SKEW_LEEWAY_SECONDS = 10
_JWKS_FETCH_TIMEOUT_SECONDS = 5.0


class JwksKeyResolver:
    """Resolve a signing key by `kid`, caching the JWKS and refetching once on a
    miss so a Supabase key rotation does not need a redeploy.

    It never fetches per request (that would be a DoS and SSRF footgun) and never
    falls back to trying every key on an unknown `kid`.
    """

    def __init__(self, fetch: JwksFetcher) -> None:
        self._fetch = fetch
        self._keys: dict[str, PyJWK] = {}

    def get(self, kid: str) -> PyJWK:
        key = self._keys.get(kid)
        if key is not None:
            return key
        self._refresh()
        rotated = self._keys.get(kid)
        if rotated is None:
            raise AuthenticationError("unknown token signing key")
        return rotated

    def _refresh(self) -> None:
        keys: dict[str, PyJWK] = {}
        for entry in self._fetch():
            kid = entry.get("kid")
            if isinstance(kid, str) and kid:
                keys[kid] = PyJWK.from_dict(entry)
        self._keys = keys


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
        resolver=JwksKeyResolver(_jwks_fetch(settings.supabase_jwks_url)),
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

"""The MCP external-caller token: a self-minted HS256 token.

This is a DIFFERENT credential from the Supabase owner JWT (different secret,
issuer, and audience). The algorithm is pinned to HS256, so a token claiming
anything else, including the ES256 Supabase JWT or an `alg=none` token, is
rejected. The audience must equal this server, so a token minted for someone
else is rejected (the confused-deputy / wrong-audience failure).

Day-1 the same service mints and verifies the token with one shared secret. The
production path is a hashed-keys table in Postgres (key hashed, linked to tenant,
scope, and expiry) so multiple AI clients can each hold their own credential; it
is written up here, not built.
"""

import time

import jwt

from app.core.errors import AuthenticationError
from app.tenants.contexts import ExternalCallerContext

_ALGORITHM = "HS256"
_CLOCK_SKEW_LEEWAY_SECONDS = 10
_DEFAULT_TTL_SECONDS = 3600


class McpTokenVerifier:
    def __init__(self, *, secret: str, issuer: str, audience: str) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> ExternalCallerContext:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("mcp token verification failed") from exc
        tenant_id = claims.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise AuthenticationError("mcp token has no tenant")
        return ExternalCallerContext(tenant_id=tenant_id)


def mint_mcp_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    tenant_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": now + ttl_seconds,
        },
        secret,
        algorithm=_ALGORITHM,
    )

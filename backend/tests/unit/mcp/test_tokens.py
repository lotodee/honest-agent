"""The MCP token: prove it refuses, and that it is NOT the Supabase JWT."""

import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core.errors import AuthenticationError
from app.mcp.tokens import McpTokenVerifier, mint_mcp_token
from app.tenants.owner_auth import JwksKeyResolver, OwnerTokenVerifier

SECRET = "mcp-signing-secret-under-test-0123456789"  # noqa: S105
ISSUER = "honest-agent"
AUDIENCE = "honest-agent-mcp"


def _verifier() -> McpTokenVerifier:
    return McpTokenVerifier(secret=SECRET, issuer=ISSUER, audience=AUDIENCE)


def _token(**overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "tenant_id": "tenant-a",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_mint_then_verify_round_trip() -> None:
    # Mint with the same secret/issuer/audience the verifier trusts, then verify:
    # the tenant survives the round trip and a re-mint still verifies.
    for tenant in ("tenant-a", "tenant-b"):
        token = mint_mcp_token(
            secret=SECRET, issuer=ISSUER, audience=AUDIENCE, tenant_id=tenant
        )
        assert _verifier().verify(token).tenant_id == tenant


def test_valid_token_resolves_tenant() -> None:
    context = _verifier().verify(
        mint_mcp_token(
            secret=SECRET, issuer=ISSUER, audience=AUDIENCE, tenant_id="tenant-a"
        )
    )
    assert context.tenant_id == "tenant-a"


def test_wrong_audience_rejected() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify(_token(aud="some-other-server"))


def test_wrong_issuer_rejected() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify(_token(iss="not-our-issuer"))


def test_expired_token_rejected() -> None:
    now = int(time.time())
    with pytest.raises(AuthenticationError):
        _verifier().verify(_token(exp=now - 3600, iat=now - 7200))


def test_wrong_secret_rejected() -> None:
    forged = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "tenant_id": "tenant-a",
            "exp": int(time.time()) + 60,
        },
        "attacker-secret-also-long-enough-0123456789",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(forged)


def test_alg_none_rejected() -> None:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {"iss": ISSUER, "aud": AUDIENCE, "tenant_id": "tenant-a"}
            ).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(f"{header}.{payload}.")


def test_missing_tenant_rejected() -> None:
    now = int(time.time())
    forged = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 60},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(forged)


def test_supabase_es256_jwt_is_rejected_by_the_mcp_verifier() -> None:
    # A Supabase owner JWT presented to /mcp must be rejected: different algorithm,
    # issuer, and audience. This is the credential-separation invariant.
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    supabase_token = jwt.encode(
        {
            "iss": "http://127.0.0.1:54321/auth/v1",
            "aud": "authenticated",
            "tenant_id": "tenant-a",
            "exp": int(time.time()) + 3600,
        },
        pem,
        algorithm="ES256",
        headers={"kid": "supabase-key"},
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(supabase_token)


def test_mcp_token_is_rejected_by_the_owner_verifier() -> None:
    # And the reverse: an MCP HS256 token presented to the owner route is rejected
    # (no kid, wrong algorithm family, wrong issuer/audience).
    _, jwk = _owner_jwk()
    owner_verifier = OwnerTokenVerifier(
        resolver=JwksKeyResolver(lambda: [dict(jwk)]),
        issuer="http://127.0.0.1:54321/auth/v1",
        audience="authenticated",
    )
    mcp_token = mint_mcp_token(
        secret=SECRET, issuer=ISSUER, audience=AUDIENCE, tenant_id="tenant-a"
    )
    with pytest.raises(AuthenticationError):
        owner_verifier.verify(mcp_token)


def _owner_jwk() -> tuple[str, dict[str, object]]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    jwk: dict[str, object] = ECAlgorithm(ECAlgorithm.SHA256).to_jwk(
        private_key.public_key(), as_dict=True
    )
    jwk.update({"kid": "owner-key", "alg": "ES256", "use": "sig"})
    return pem, jwk

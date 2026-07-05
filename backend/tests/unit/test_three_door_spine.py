"""The spine: across all three doors the tenant comes ONLY from the credential.

No request input (body field, header, claim a client controls) may set or change
the resolved tenant. This consolidates the invariant each door's own tests prove.
"""

import json
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.mcp.tokens import McpTokenVerifier, mint_mcp_token
from app.tenants.gate import VisitorGate
from app.tenants.owner_auth import JwksKeyResolver, OwnerTokenVerifier
from app.tenants.rate_limit import AllowAllRateLimiter
from app.tenants.widget_keys import InMemoryWidgetKeyStore, WidgetKeyRecord

MCP_SECRET = "spine-mcp-secret-long-enough-0123456789"  # noqa: S105


async def test_owner_tenant_comes_only_from_app_metadata() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    jwk: dict[str, object] = ECAlgorithm(ECAlgorithm.SHA256).to_jwk(
        private_key.public_key(), as_dict=True
    )
    jwk.update({"kid": "k", "alg": "ES256", "use": "sig"})
    verifier = OwnerTokenVerifier(
        resolver=JwksKeyResolver(lambda: [dict(jwk)], cooldown_seconds=300.0),
        issuer="iss",
        audience="aud",
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "iss",
            "aud": "aud",
            "sub": "user-1",
            "iat": now,
            "exp": now + 600,
            "app_metadata": {"tenant_id": "tenant-a"},
            "user_metadata": {"tenant_id": "tenant-b"},
        },
        pem,
        algorithm="ES256",
        headers={"kid": "k"},
    )
    assert verifier.verify(token).tenant_id == "tenant-a"


async def test_visitor_tenant_cannot_be_overridden_by_the_body() -> None:
    gate = VisitorGate(
        store=InMemoryWidgetKeyStore(
            {"wk": WidgetKeyRecord("tenant-a", frozenset({"tenant-a.example.com"}))}
        ),
        rate_limiter=AllowAllRateLimiter(),
        max_body_bytes=65536,
    )
    context = await gate.authorize(
        widget_key="wk",
        origin="https://tenant-a.example.com",
        referer=None,
        client_ip=None,
        body=json.dumps({"query": "q", "tenant_id": "tenant-b"}).encode(),
    )
    assert context.tenant_id == "tenant-a"


def test_mcp_tenant_comes_only_from_the_token_claim() -> None:
    verifier = McpTokenVerifier(secret=MCP_SECRET, issuer="iss", audience="aud")
    token = mint_mcp_token(
        secret=MCP_SECRET, issuer="iss", audience="aud", tenant_id="tenant-a"
    )
    assert verifier.verify(token).tenant_id == "tenant-a"

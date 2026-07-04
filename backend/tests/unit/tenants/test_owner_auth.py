"""Owner JWT verification: the one real login. The rejects matter most."""

import base64
import hashlib
import hmac
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm
from starlette.requests import Request

from app.core.errors import AuthenticationError, ServiceUnavailableError
from app.tenants.owner_auth import (
    JwksKeyResolver,
    OwnerTokenVerifier,
    _jwks_fetch,
    bearer_token,
)

ISSUER = "https://issuer.test/auth/v1"
AUDIENCE = "authenticated"
KID = "key-1"

Jwk = dict[str, object]


def _ec_keypair(kid: str) -> tuple[str, Jwk]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    jwk: Jwk = ECAlgorithm(ECAlgorithm.SHA256).to_jwk(
        private_key.public_key(), as_dict=True
    )
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig", "public_pem": public_pem})
    return pem, jwk


def _verifier(keys: list[Jwk]) -> OwnerTokenVerifier:
    return OwnerTokenVerifier(
        resolver=JwksKeyResolver(lambda: [dict(k) for k in keys]),
        issuer=ISSUER,
        audience=AUDIENCE,
    )


def _claims(**overrides: object) -> dict[str, object]:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 3600,
        "iat": now,
        "sub": "user-1",
        "app_metadata": {"tenant_id": "tenant-a"},
    }
    claims.update(overrides)
    return claims


def _mint(
    pem: str, claims: dict[str, object], *, kid: str = KID, alg: str = "ES256"
) -> str:
    return jwt.encode(claims, pem, algorithm=alg, headers={"kid": kid})


def _b64(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_valid_token_resolves_tenant_from_app_metadata() -> None:
    pem, jwk = _ec_keypair(KID)
    context = _verifier([jwk]).verify(_mint(pem, _claims()))
    assert context.tenant_id == "tenant-a"
    assert context.user_id == "user-1"


def test_bad_signature_rejected() -> None:
    _, jwk = _ec_keypair(KID)
    attacker_pem, _ = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(attacker_pem, _claims()))


def test_wrong_issuer_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(iss="https://evil.test/auth/v1")))


def test_wrong_audience_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(aud="some-other-service")))


def test_expired_token_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    now = int(time.time())
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(exp=now - 3600, iat=now - 7200)))


def test_future_nbf_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(nbf=int(time.time()) + 3600)))


def test_future_iat_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(iat=int(time.time()) + 3600)))


def test_alg_none_rejected() -> None:
    _, jwk = _ec_keypair(KID)
    header = _b64({"alg": "none", "typ": "JWT", "kid": KID})
    forged = f"{header}.{_b64(_claims())}."
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(forged)


def test_algorithm_confusion_hs256_with_public_key_rejected() -> None:
    # The classic bypass: re-sign as HS256 using the public key bytes as the HMAC
    # secret. PyJWT's encode refuses this, so forge it by hand exactly as an
    # attacker would. The verifier must reject it because it pins ES256.
    _, jwk = _ec_keypair(KID)
    public_pem = jwk["public_pem"]
    assert isinstance(public_pem, str)
    header = _b64({"alg": "HS256", "typ": "JWT", "kid": KID})
    payload = _b64(_claims())
    signing_input = f"{header}.{payload}".encode()
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(public_pem.encode(), signing_input, hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(f"{header}.{payload}.{signature}")


def test_missing_kid_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    token = jwt.encode(_claims(), pem, algorithm="ES256")
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(token)


def test_unknown_kid_rejected_without_trying_every_key() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(), kid="some-other-kid"))


def test_tenant_only_in_user_metadata_is_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    claims = _claims(app_metadata={}, user_metadata={"tenant_id": "tenant-a"})
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, claims))


def test_app_metadata_wins_over_user_metadata() -> None:
    pem, jwk = _ec_keypair(KID)
    claims = _claims(
        app_metadata={"tenant_id": "tenant-a"},
        user_metadata={"tenant_id": "tenant-b"},
    )
    context = _verifier([jwk]).verify(_mint(pem, claims))
    assert context.tenant_id == "tenant-a"


def test_missing_app_metadata_tenant_rejected() -> None:
    pem, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify(_mint(pem, _claims(app_metadata={"role": "x"})))


def test_malformed_token_rejected() -> None:
    _, jwk = _ec_keypair(KID)
    with pytest.raises(AuthenticationError):
        _verifier([jwk]).verify("not-a-jwt")


def test_unknown_kid_flood_triggers_at_most_one_jwks_fetch() -> None:
    # The HIGH: an anonymous flood of tokens carrying random unknown kids (read from
    # the unverified header) must NOT amplify into one outbound JWKS fetch per request.
    pem, jwk = _ec_keypair(KID)
    fetches = {"n": 0}

    def fetch() -> list[Jwk]:
        fetches["n"] += 1
        return [dict(jwk)]

    # A fixed clock keeps every request inside one cooldown window.
    resolver = JwksKeyResolver(fetch, cooldown_seconds=300.0, clock=lambda: 1000.0)
    verifier = OwnerTokenVerifier(resolver=resolver, issuer=ISSUER, audience=AUDIENCE)

    for i in range(100):
        with pytest.raises(AuthenticationError):
            verifier.verify(_mint(pem, _claims(), kid=f"random-kid-{i}"))
    assert fetches["n"] <= 1


def test_rotated_key_is_picked_up_after_the_cooldown() -> None:
    pem1, jwk1 = _ec_keypair("key-1")
    pem2, jwk2 = _ec_keypair("key-2")
    published: list[Jwk] = [jwk1]
    fetches = {"n": 0}

    def fetch() -> list[Jwk]:
        fetches["n"] += 1
        return [dict(k) for k in published]

    clock = {"t": 1000.0}
    resolver = JwksKeyResolver(fetch, cooldown_seconds=300.0, clock=lambda: clock["t"])
    verifier = OwnerTokenVerifier(resolver=resolver, issuer=ISSUER, audience=AUDIENCE)

    assert verifier.verify(_mint(pem1, _claims(), kid="key-1")).tenant_id == "tenant-a"
    assert fetches["n"] == 1

    # key-2 is rotated in, but WITHIN the cooldown the resolver must not refetch.
    published.append(jwk2)
    clock["t"] += 100.0
    with pytest.raises(AuthenticationError):
        verifier.verify(_mint(pem2, _claims(), kid="key-2"))
    assert fetches["n"] == 1  # still throttled: no extra outbound fetch

    # After the cooldown elapses, the first miss refetches and picks up the rotation.
    clock["t"] += 300.0
    assert verifier.verify(_mint(pem2, _claims(), kid="key-2")).tenant_id == "tenant-a"
    assert fetches["n"] == 2


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": raw,
        }
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
        {"Authorization": ""},
    ],
)
def test_bearer_token_rejects_missing_or_malformed(headers: dict[str, str]) -> None:
    with pytest.raises(AuthenticationError):
        bearer_token(_request(headers))


def test_bearer_token_extracts_value() -> None:
    assert bearer_token(_request({"Authorization": "Bearer the-token"})) == "the-token"


def test_jwks_fetch_surfaces_a_network_failure() -> None:
    # The resolver is load-bearing; a JWKS endpoint that is unreachable or hangs
    # must surface as an error (fetch is time-bounded), never a silent success.
    fetch = _jwks_fetch("http://127.0.0.1:1/.well-known/jwks.json")
    with pytest.raises(httpx.HTTPError):
        fetch()


def test_resolver_fails_closed_when_jwks_fetch_errors() -> None:
    # If keys cannot be fetched, get() must RAISE, never return a key or None that
    # would let verification proceed. No JWKS, no accepted token. The raw fetch
    # failure is converted to a clean, retryable 503 (not a raw exception → 500).
    def failing_fetch() -> list[Jwk]:
        raise TimeoutError("jwks endpoint timed out")

    with pytest.raises(ServiceUnavailableError):
        JwksKeyResolver(failing_fetch).get("key-1")


def test_failing_jwks_endpoint_raises_clean_503_and_is_still_throttled() -> None:
    # A down/hanging JWKS endpoint on the FIRST hit must surface a mapped
    # ServiceUnavailableError (RFC 9457 renders it), never a raw httpx exception that
    # falls through to a generic 500. And because the attempt is stamped before the
    # fetch, a second miss within the cooldown is throttled: no second outbound call.
    fetches = {"n": 0}

    def failing_fetch() -> list[Jwk]:
        fetches["n"] += 1
        raise httpx.ConnectError("jwks endpoint refused the connection")

    resolver = JwksKeyResolver(
        failing_fetch, cooldown_seconds=300.0, clock=lambda: 1000.0
    )
    with pytest.raises(ServiceUnavailableError):
        resolver.get("key-1")
    assert fetches["n"] == 1
    with pytest.raises(AuthenticationError):
        resolver.get("key-2")  # throttled: clean reject, no second fetch
    assert fetches["n"] == 1

"""Owner JWT verification: the one real login. The rejects matter most."""

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm
from starlette.requests import Request

from app.core.errors import AuthenticationError
from app.tenants.owner_auth import JwksKeyResolver, OwnerTokenVerifier, bearer_token

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


def test_resolver_refetches_once_on_key_rotation() -> None:
    pem1, jwk1 = _ec_keypair("key-1")
    pem2, jwk2 = _ec_keypair("key-2")
    published: list[list[Jwk]] = [[jwk1], [jwk1, jwk2]]
    calls = {"n": 0}

    def fetch() -> list[Jwk]:
        current = published[min(calls["n"], len(published) - 1)]
        calls["n"] += 1
        return [dict(k) for k in current]

    verifier = OwnerTokenVerifier(
        resolver=JwksKeyResolver(fetch), issuer=ISSUER, audience=AUDIENCE
    )
    assert verifier.verify(_mint(pem1, _claims(), kid="key-1")).tenant_id == "tenant-a"
    # key-2 was rotated in after the first fetch; a cache miss refetches once.
    assert verifier.verify(_mint(pem2, _claims(), kid="key-2")).tenant_id == "tenant-a"


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

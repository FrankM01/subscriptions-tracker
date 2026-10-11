"""Authentication tests for Keycloak JWT validation and route protection."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
import pytest
from fastapi import HTTPException

from app import auth
from app.routers.subscriptions import router as subscriptions_router


ISSUER = "http://127.0.0.1:8081/realms/subscriptions"
AUDIENCE = "subscriptions-api"


@pytest.fixture
def signing_keys():
    return (
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
    )


@pytest.fixture
def configured_jwks(monkeypatch, signing_keys):
    private_key, _ = signing_keys
    public_key = private_key.public_key()
    monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "http://127.0.0.1:8081")
    monkeypatch.setenv("KEYCLOAK_REALM", "subscriptions")
    monkeypatch.setenv("KEYCLOAK_WEB_CLIENT_ID", "subscriptions-web")
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", ISSUER)
    monkeypatch.setenv(
        "KEYCLOAK_JWKS_URL",
        "http://keycloak:8080/realms/subscriptions/protocol/openid-connect/certs",
    )
    monkeypatch.setenv("KEYCLOAK_API_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("SUBSCRIPTIONS_ENV", raising=False)

    class TestJwksClient:
        def get_signing_key_from_jwt(self, _token):
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(auth, "_get_jwks_client", lambda _url: TestJwksClient())
    return private_key


def encode_token(private_key, **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "sub": "user-123",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "preferred_username": "local-user",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_valid_access_token_returns_verified_claims(configured_jwks):
    token = encode_token(configured_jwks)

    claims = auth.validate_access_token(token)

    assert claims["sub"] == "user-123"
    assert claims["preferred_username"] == "local-user"


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"iss": "http://wrong-issuer/realms/test"},
        {"aud": "another-api"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_token_with_wrong_issuer_audience_or_expiry_is_rejected(
    configured_jwks, claim_overrides
):
    token = encode_token(configured_jwks, **claim_overrides)

    with pytest.raises(HTTPException) as error:
        auth.validate_access_token(token)

    assert error.value.status_code == 401


def test_token_with_invalid_signature_is_rejected(configured_jwks, signing_keys):
    token = encode_token(signing_keys[1])

    with pytest.raises(HTTPException) as error:
        auth.validate_access_token(token)

    assert error.value.status_code == 401


def test_malformed_token_is_rejected_without_fetching_jwks(configured_jwks, monkeypatch):
    monkeypatch.setattr(
        auth,
        "_get_jwks_client",
        lambda _url: pytest.fail("JWKS must not be requested for malformed tokens"),
    )

    with pytest.raises(HTTPException) as error:
        auth.validate_access_token("not-a-jwt")

    assert error.value.status_code == 401


def test_subscription_routes_reject_missing_bearer_token():
    protected_app = FastAPI()
    protected_app.include_router(subscriptions_router)

    response = TestClient(protected_app).get("/subscriptions")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_public_config_exposes_only_browser_required_values(configured_jwks):
    config = auth.get_public_auth_config()

    assert config == {
        "enabled": True,
        "url": "http://127.0.0.1:8081",
        "realm": "subscriptions",
        "clientId": "subscriptions-web",
    }
    assert "jwksUrl" not in config
    assert "apiAudience" not in config


def test_missing_oidc_settings_fail_closed(monkeypatch):
    for key in (
        "KEYCLOAK_PUBLIC_URL",
        "KEYCLOAK_REALM",
        "KEYCLOAK_WEB_CLIENT_ID",
        "KEYCLOAK_ISSUER_URL",
        "KEYCLOAK_JWKS_URL",
        "KEYCLOAK_API_AUDIENCE",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(HTTPException) as error:
        auth.get_public_auth_config()

    assert error.value.status_code == 503

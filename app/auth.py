"""Validate Keycloak access tokens and expose the public login configuration."""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import (
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
)


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class KeycloakSettings:
    public_url: str
    realm: str
    web_client_id: str
    issuer_url: str
    jwks_url: str
    api_audience: str

    def public_config(self) -> dict[str, str | bool]:
        return {
            "enabled": True,
            "url": self.public_url,
            "realm": self.realm,
            "clientId": self.web_client_id,
        }


def get_keycloak_settings() -> KeycloakSettings | None:
    """Load public and server-side OIDC settings without exposing secrets."""
    values = {
        "public_url": os.getenv("KEYCLOAK_PUBLIC_URL", "").rstrip("/"),
        "realm": os.getenv("KEYCLOAK_REALM", ""),
        "web_client_id": os.getenv("KEYCLOAK_WEB_CLIENT_ID", ""),
        "issuer_url": os.getenv("KEYCLOAK_ISSUER_URL", "").rstrip("/"),
        "jwks_url": os.getenv("KEYCLOAK_JWKS_URL", ""),
        "api_audience": os.getenv("KEYCLOAK_API_AUDIENCE", ""),
    }
    if not all(values.values()):
        return None
    return KeycloakSettings(**values)


def get_public_auth_config() -> dict[str, str | bool]:
    """Return the small, non-secret config that the browser needs to log in."""
    if os.getenv("SUBSCRIPTIONS_ENV") == "test":
        return {"enabled": False}
    settings = get_keycloak_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación no está configurada.",
        )
    return settings.public_config()


@lru_cache(maxsize=8)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, timeout=5)


def validate_access_token(token: str) -> dict[str, Any]:
    """Verify signature and required claims for a Keycloak API access token."""
    settings = get_keycloak_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación no está configurada.",
        )

    try:
        jwt.get_unverified_header(token)
    except InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        signing_key = _get_jwks_client(settings.jwks_url).get_signing_key_from_jwt(token)
    except PyJWKClientConnectionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo consultar la clave de autenticación.",
        ) from error
    except PyJWKClientError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.issuer_url,
            audience=settings.api_audience,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Authenticate a bearer token; used as a dependency on protected routes."""
    if os.getenv("SUBSCRIPTIONS_ENV") == "test":
        return {"sub": "test-user"}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return validate_access_token(credentials.credentials)

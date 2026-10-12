"""Opt-in API authorization and CRUD coverage against an isolated PostgreSQL schema."""

from datetime import timedelta
from decimal import Decimal
import os
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app import auth, main
from app.auth import get_current_user
from app.database import DEFAULT_DATABASE_PATH, make_engine
from app.repositories.subscription_repository import SubscriptionRepository
from app.routers.subscriptions import set_service
from app.services.subscription_service import SubscriptionService
from app.utils.dates import today_in_lima


PROJECT_ROOT = DEFAULT_DATABASE_PATH.parent.parent
POSTGRES_TEST_URL = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")
ISSUER = "https://issuer.example.test/realms/subscriptions"
AUDIENCE = "subscriptions-api"


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="set SUBSCRIPTIONS_TEST_POSTGRES_URL to run PostgreSQL integration coverage",
)
def test_protected_subscription_lifecycle_with_valid_and_invalid_tokens(
    monkeypatch,
):
    base_url = make_url(POSTGRES_TEST_URL)
    schema = f"test_authenticated_api_{uuid4().hex}"
    admin_engine = make_engine(base_url.render_as_string(hide_password=False))
    test_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

        scoped_url = base_url.update_query_dict(
            {"options": f"-csearch_path={schema}"}
        ).render_as_string(hide_password=False)
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", scoped_url)
        monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
        monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "https://issuer.example.test")
        monkeypatch.setenv("KEYCLOAK_REALM", "subscriptions")
        monkeypatch.setenv("KEYCLOAK_WEB_CLIENT_ID", "subscriptions-web")
        monkeypatch.setenv("KEYCLOAK_ISSUER_URL", ISSUER)
        monkeypatch.setenv("KEYCLOAK_JWKS_URL", f"{ISSUER}/protocol/openid-connect/certs")
        monkeypatch.setenv("KEYCLOAK_API_AUDIENCE", AUDIENCE)

        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
        test_engine = make_engine(scoped_url)
        original_service = main.service
        set_service(SubscriptionService(SubscriptionRepository(test_engine)))

        signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        monkeypatch.setattr(
            auth,
            "_get_jwks_client",
            lambda _jwks_url: SimpleNamespace(
                get_signing_key_from_jwt=lambda _token: SimpleNamespace(
                    key=signing_key.public_key()
                )
            ),
        )
        main.app.dependency_overrides.pop(get_current_user, None)

        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "postgres-integration-user",
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 300,
        }
        valid_token = jwt.encode(claims, signing_key, algorithm="RS256")
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        invalid_signature_token = jwt.encode(claims, wrong_key, algorithm="RS256")
        headers = {"Authorization": f"Bearer {valid_token}"}
        renewal_date = today_in_lima() + timedelta(days=30)

        with TestClient(main.app) as client:
            assert client.get("/subscriptions").status_code == 401
            assert client.get(
                "/subscriptions",
                headers={"Authorization": "Bearer not-a-jwt"},
            ).status_code == 401
            assert client.get(
                "/subscriptions",
                headers={"Authorization": f"Bearer {invalid_signature_token}"},
            ).status_code == 401

            created = client.post(
                "/subscriptions",
                headers=headers,
                json={
                    "name": "PostgreSQL authenticated lifecycle",
                    "cost": "9.99",
                    "billing_cycle": "monthly",
                    "renewal_date": renewal_date.isoformat(),
                },
            )
            assert created.status_code == 201, created.text
            subscription_id = created.json()["subscription_id"]

            listed = client.get("/subscriptions", headers=headers)
            assert listed.status_code == 200
            assert [item["subscription_id"] for item in listed.json()] == [
                subscription_id
            ]

            updated = client.put(
                f"/subscriptions/{subscription_id}",
                headers=headers,
                json={"cost": "12.50"},
            )
            assert updated.status_code == 200
            assert Decimal(updated.json()["cost"]) == Decimal("12.50")

            renewal = client.post(
                f"/subscriptions/{subscription_id}/renewals",
                headers=headers,
                json={
                    "scheduled_date": renewal_date.isoformat(),
                    "paid_date": today_in_lima().isoformat(),
                },
            )
            assert renewal.status_code == 201, renewal.text
            history = client.get(
                f"/subscriptions/{subscription_id}/renewals", headers=headers
            )
            assert history.status_code == 200
            assert len(history.json()) == 1

            deleted = client.delete(
                f"/subscriptions/{subscription_id}", headers=headers
            )
            assert deleted.status_code == 204
            assert client.get("/subscriptions", headers=headers).json() == []
    finally:
        set_service(original_service) if "original_service" in locals() else None
        if test_engine is not None:
            test_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            admin_engine.dispose()

"""Utility API, migrations and competing writes against isolated PG schemas."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app import auth
from app.auth import get_current_user
from app.database import DEFAULT_DATABASE_PATH, make_engine
from app.main import app
from app.models.utility import UtilityCreate, UtilityEntryCreate, UtilityPaymentConfirmation
from app.repositories.utility_repository import UtilityEntryConflictError, UtilityRepository
from app.routers.utilities import get_service
from app.services.utility_service import UtilityService


POSTGRES_TEST_URL = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_TEST_URL, reason="set SUBSCRIPTIONS_TEST_POSTGRES_URL")


@pytest.fixture
def postgres_utilities(monkeypatch):
    base_url = make_url(POSTGRES_TEST_URL)
    schema = f"test_utilities_{uuid4().hex}"
    admin = make_engine(base_url.render_as_string(hide_password=False))
    engine = None
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = base_url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", url)
        config = Config(str(DEFAULT_DATABASE_PATH.parent.parent / "alembic.ini"))
        command.upgrade(config, "406d989e7e68")
        engine = make_engine(url)
        # Exercise an actual upgrade with pre-existing subscriptions and payments.
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO subscriptions (subscription_id, name, cost_cents, billing_cycle, "
                "renewal_date, anchor_day, is_active) VALUES "
                "('existing', 'Existing subscription', 1234, 'monthly', '2025-12-01', 1, true)"
            ))
            connection.execute(text(
                "INSERT INTO renewals (subscription_id, scheduled_date, paid_date, paid_amount_cents, "
                "resulting_renewal_date, resulting_billing_cycle, resulting_anchor_day) VALUES "
                "('existing', '2025-11-01', '2025-11-01', 1234, '2025-12-01', 'monthly', 1)"
            ))
        command.upgrade(config, "head")
        command.check(config)
        repository = UtilityRepository(engine)
        app.dependency_overrides[get_service] = lambda: UtilityService(repository)
        with TestClient(app) as client:
            yield engine, repository, client, config
    finally:
        app.dependency_overrides.pop(get_service, None)
        if engine is not None:
            engine.dispose()
        try:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            admin.dispose()


def test_authenticated_postgres_utility_lifecycle(postgres_utilities, monkeypatch):
    engine, _, client, _ = postgres_utilities
    monkeypatch.delitem(app.dependency_overrides, get_current_user)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    issuer = "https://issuer.example.test/realms/subscriptions"
    for name, value in {
        "KEYCLOAK_PUBLIC_URL": "https://issuer.example.test",
        "KEYCLOAK_REALM": "subscriptions", "KEYCLOAK_WEB_CLIENT_ID": "subscriptions-web",
        "KEYCLOAK_ISSUER_URL": issuer, "KEYCLOAK_JWKS_URL": issuer + "/certs",
        "KEYCLOAK_API_AUDIENCE": "subscriptions-api",
    }.items():
        monkeypatch.setenv(name, value)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "_get_jwks_client", lambda _: SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()),
    ))
    now = int(time.time())
    token = jwt.encode({"iss": issuer, "sub": "utility-test-user", "aud": "subscriptions-api",
                        "iat": now, "exp": now + 300}, key, algorithm="RS256")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/utilities").status_code == 401
    assert client.get("/utilities/summary?year=2025&month=11").status_code == 401
    assert client.get("/utilities", headers={"Authorization": "Bearer invalid"}).status_code == 401
    created = client.post("/utilities", headers=headers, json={"name": "Luz"})
    assert created.status_code == 201
    uid = created.json()["utility_id"]
    base = f"/utilities/{uid}"
    assert client.get(base, headers=headers).json() == created.json()
    assert client.patch(base, headers=headers, json={"provider": "Proveedor"}).status_code == 200
    entry = client.post(base + "/entries", headers=headers,
                        json={"year": 2025, "month": 11, "amount": "45.10"})
    assert entry.status_code == 201
    path = base + "/entries/" + entry.json()["entry_id"]
    assert client.post(base + "/entries", headers=headers,
                       json={"year": 2025, "month": 11, "amount": "20"}).status_code == 409
    assert client.patch(path, headers=headers, json={"amount": "46.20"}).status_code == 200
    paid = client.post(path + "/confirm", headers=headers,
                       json={"paid_date": "2025-12-02", "amount": "47.30"})
    assert paid.status_code == 200
    assert client.post(path + "/confirm", headers=headers, json={}).status_code == 409
    assert client.patch(base, headers=headers, json={"is_active": False}).status_code == 200
    summary = client.get("/utilities/summary?year=2025&month=11", headers=headers)
    assert summary.status_code == 200
    assert summary.json() == {"year": 2025, "month": 11, "pending_count": 0, "paid_count": 1,
                              "total_pending": "0.00", "total_paid": "47.30"}
    assert client.get("/utilities/summary?year=2025&month=12", headers=headers).json()["paid_count"] == 0
    engine.dispose()
    assert client.get(base + "/entries", headers=headers).json() == [paid.json()]
    assert client.post(path + "/undo", headers=headers).json()["status"] == "pending"
    assert client.post(path + "/undo", headers=headers).status_code == 409
    assert client.get("/utilities/summary?year=2025&month=11", headers=headers).json()["total_pending"] == "47.30"
    assert client.patch(base, headers=headers, json={"is_active": True}).status_code == 200


@pytest.mark.parametrize("operation", ["create", "confirm", "undo"])
def test_postgres_serializes_competing_monthly_writes(postgres_utilities, operation):
    _, repository, _, _ = postgres_utilities
    utility = UtilityService(repository).create(UtilityCreate(name="Agua"))
    uid = str(utility.utility_id)
    entry = None
    if operation != "create":
        entry = repository.create_entry(uid, UtilityEntryCreate(year=2025, month=11, amount="45.10"))
        if operation == "undo":
            repository.confirm_payment(uid, str(entry.entry_id), UtilityPaymentConfirmation())
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=10)
        try:
            if operation == "create":
                result = repository.create_entry(uid, UtilityEntryCreate(year=2025, month=11, amount="45.10"))
            elif operation == "confirm":
                result = repository.confirm_payment(uid, str(entry.entry_id), UtilityPaymentConfirmation())
            else:
                result = repository.undo_payment(uid, str(entry.entry_id))
            return result.status
        except UtilityEntryConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert sorted(results) == sorted(["paid" if operation == "confirm" else "pending", "conflict"])
    assert len(repository.list_entries(uid)) == 1


def test_postgres_constraints_rollback_and_reversible_migration(postgres_utilities):
    engine, repository, client, config = postgres_utilities
    utility = UtilityService(repository).create(UtilityCreate(name="Gas"))
    uid = str(utility.utility_id)
    first = repository.create_entry(uid, UtilityEntryCreate(year=2025, month=11, amount="1.10"))
    second = repository.create_entry(uid, UtilityEntryCreate(year=2025, month=12, amount="2.20"))
    path = f"/utilities/{uid}/entries/{second.entry_id}"
    assert client.patch(path, json={"month": 11, "amount": "999"}).status_code == 409
    assert repository.list_entries(uid)[0].amount == Decimal("2.20")
    insert = text("INSERT INTO utility_entries (entry_id, utility_id, year, month, amount_cents) "
                  "VALUES (:entry_id, :utility_id, :year, :month, :amount_cents)")
    for overrides in ({}, {"month": 0}, {"month": 10, "amount_cents": 0},
                      {"month": 10, "utility_id": str(uuid4())}):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(insert, {"entry_id": str(uuid4()), "utility_id": uid,
                                       "year": 2025, "month": 11, "amount_cents": 110, **overrides})
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM utilities WHERE utility_id=:uid"), {"uid": uid})
    assert len(repository.list_entries(uid)) == 2
    command.downgrade(config, "406d989e7e68")
    assert set(inspect(engine).get_table_names()) == {"subscriptions", "renewals", "alembic_version"}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT cost_cents FROM subscriptions WHERE subscription_id='existing'")) == 1234
        assert connection.scalar(text("SELECT count(*) FROM renewals")) == 1
    command.upgrade(config, "head")
    command.check(config)

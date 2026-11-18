"""Loan API and competing transactions on disposable SQLite/PostgreSQL databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
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
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app import auth
from app.auth import get_current_user
from app.database import DEFAULT_DATABASE_PATH, make_engine
from app.main import app
from app.models.debt import DebtCreate, DebtPaymentConfirmation, DebtUpdate
from app.repositories.debt_repository import DebtConflictError, DebtNotFoundError, DebtRepository
from app.routers.debts import get_service
from app.services.debt_service import DebtService
from app.utils.dates import today_in_lima


@pytest.fixture(params=["sqlite", "postgres"])
def debts(request, tmp_path, monkeypatch):
    admin = None
    engine = None
    schema = f"test_debts_{uuid4().hex}"
    if request.param == "postgres":
        configured = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")
        if not configured:
            pytest.skip("set SUBSCRIPTIONS_TEST_POSTGRES_URL")
        base = make_url(configured)
        admin = make_engine(configured)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = base.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'debts.db'}"
    try:
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", url)
        config = Config(str(DEFAULT_DATABASE_PATH.parent.parent / "alembic.ini"))
        command.upgrade(config, "7b21c9d840ef")
        engine = make_engine(url)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO utilities (utility_id, name) VALUES ('old', 'Luz')"))
        command.upgrade(config, "head")
        command.check(config)
        repository = DebtRepository(engine)
        service = DebtService(repository)
        app.dependency_overrides[get_service] = lambda: service
        with TestClient(app) as client:
            yield client, repository, engine, config
    finally:
        app.dependency_overrides.pop(get_service, None)
        if engine is not None:
            engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            admin.dispose()


def create(client, **changes):
    response = client.post("/debts", json={
        "name": "Préstamo", "creditor": "Persona", "installment_amount": "100.25",
        "total_installments": 6, "previously_paid_installments": 1,
        "first_due_date": "2025-01-31", **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_lifecycle_progress_archive_prepay_settle_and_undo(debts):
    client, _, engine, _ = debts
    debt = create(client)
    base = f"/debts/{debt['debt_id']}"
    assert debt["paid_installments"] == 1
    assert debt["pending_installments"] == 5
    assert debt["remaining_balance"] == "501.25"
    assert debt["overdue_installments"] == 5
    assert [r["number"] for r in debt["installments"]] == [2, 3, 4, 5, 6]
    assert [r["due_date"] for r in debt["installments"][:3]] == ["2025-01-31", "2025-02-28", "2025-03-31"]
    assert all(r["paid_date"] is None for r in debt["installments"])
    assert client.get(base).json() == debt
    assert client.get(base + "/installments").json() == debt["installments"]
    assert client.patch(base, json={"is_active": False}).json()["is_active"] is False
    assert client.get("/debts?is_active=true").json() == []
    assert len(client.get("/debts?is_active=false").json()) == 1
    for row in debt["installments"]:
        path = base + "/installments/" + row["installment_id"]
        # Prepayment and out-of-order confirmations are allowed, even when archived.
        assert client.post(path + "/confirm", json={"paid_date": "2024-12-01"}).status_code == 200
        assert client.post(path + "/confirm", json={}).status_code == 409
    final = client.get(base).json()
    assert final["paid_installments"] == 6
    assert final["remaining_balance"] == "0.00"
    assert final["status"] == "settled"
    assert final["next_due_date"] is None
    assert final["schedule_editable"] is False
    path = base + "/installments/" + debt["installments"][0]["installment_id"]
    assert client.patch(path, json={"paid_date": "2024-12-02"}).json()["paid_date"] == "2024-12-02"
    assert client.post(path + "/undo").json()["status"] == "pending"
    assert client.post(path + "/undo").status_code == 409
    reopened = client.get(base).json()
    assert reopened["status"] == "pending" and reopened["paid_installments"] == 5
    assert reopened["remaining_balance"] == "100.25"
    assert reopened["next_due_date"] == "2025-01-31"
    assert client.patch(base, json={"is_active": True}).json()["is_active"] is True
    engine.dispose()
    assert client.get(base).json()["installments"] == reopened["installments"]
    second = create(client, name="Otro préstamo")
    assert second["creditor"] == debt["creditor"]
    assert len(client.get("/debts").json()) == 2


def test_schedule_correction_and_payment_lock(debts):
    client, _, _, _ = debts
    debt = create(client)
    base = f"/debts/{debt['debt_id']}"
    edited = client.patch(base, json={
        "installment_amount": "20.00", "total_installments": 3,
        "first_due_date": "2024-01-31",
    })
    assert edited.status_code == 200, edited.text
    debt = edited.json()
    assert [r["due_date"] for r in debt["installments"]] == ["2024-01-31", "2024-02-29"]
    assert debt["remaining_balance"] == "40.00"
    path = base + "/installments/" + debt["installments"][0]["installment_id"]
    assert client.patch(path, json={"paid_date": "2024-01-01"}).status_code == 409
    assert client.post(path + "/confirm", json={}).json()["paid_date"] == today_in_lima().isoformat()
    for change in ({"installment_amount": "30"}, {"first_due_date": "2024-02-01"},
                   {"total_installments": 4}, {"previously_paid_installments": 0}):
        assert client.patch(base, json={"name": "Should roll back", **change}).status_code == 409
        assert client.get(base).json()["name"] == "Préstamo"
    assert client.patch(base, json={"name": "Personal", "creditor": "Otra persona", "notes": "  nota  "}).json()["notes"] == "nota"
    assert client.post(path + "/undo").status_code == 200
    assert client.get(base).json()["schedule_editable"] is True
    assert client.patch(base, json={"installment_amount": "30"}).json()["remaining_balance"] == "60.00"
    before = client.get(base).json()
    assert client.patch(base, json={"total_installments": 0}).status_code == 422
    assert client.patch(base, json={"previously_paid_installments": 4}).status_code == 422
    assert client.get(base).json() == before
    settled = client.patch(base, json={"previously_paid_installments": 3, "first_due_date": None})
    assert settled.status_code == 200
    assert settled.json()["status"] == "settled" and settled.json()["installments"] == []


def test_summary_uses_due_month_includes_archive_and_no_declared_cash(debts):
    client, _, _, _ = debts
    assert client.get("/debts/summary?year=2025&month=2").json()["total_pending"] == "0.00"
    debt = create(client)
    base = f"/debts/{debt['debt_id']}"
    row = debt["installments"][1]
    client.patch(base, json={"is_active": False})
    summary = client.get("/debts/summary?year=2025&month=2").json()
    assert summary == {"year": 2025, "month": 2, "pending_count": 1, "paid_count": 0,
                       "total_pending": "100.25", "total_paid": "0.00",
                       "overdue_before_month_count": 1, "total_overdue_before_month": "100.25"}
    path = base + "/installments/" + row["installment_id"]
    client.post(path + "/confirm", json={"paid_date": "2025-03-02"})
    paid = client.get("/debts/summary?year=2025&month=2").json()
    assert paid["total_paid"] == "100.25" and paid["pending_count"] == 0
    assert client.get("/debts/summary?year=2025&month=3").json()["paid_count"] == 0
    assert client.get("/debts/summary?year=2024&month=12").json()["paid_count"] == 0
    assert client.get("/debts/summary?year=9999&month=12").status_code == 200
    assert client.get("/debts/summary?year=2025&month=13").status_code == 422
    assert client.get("/debts/summary").status_code == 422


@pytest.mark.parametrize("changes", [
    {"installment_amount": "0"}, {"installment_amount": "1.001"},
    {"installment_amount": "10000000"}, {"total_installments": True},
    {"previously_paid_installments": 7}, {"first_due_date": None},
    {"first_due_date": "9999-12-01"}, {"creditor": " "}, {"unexpected": 1},
])
def test_invalid_create_has_no_rows(debts, changes):
    client, _, _, _ = debts
    response = client.post("/debts", json={
        "name": "Loan", "creditor": "Person", "installment_amount": "10",
        "total_installments": 6, "previously_paid_installments": 1,
        "first_due_date": "2025-01-01", **changes,
    })
    assert response.status_code == 422
    assert client.get("/debts").json() == []


def test_invalid_payments_missing_rows_and_nullable_updates(debts):
    client, _, _, _ = debts
    debt = create(client)
    base = f"/debts/{debt['debt_id']}"
    path = base + "/installments/" + debt["installments"][0]["installment_id"]
    for payload in ({}, {"name": None}, {"is_active": "false"}, {"first_due_date": None}):
        assert client.patch(base, json=payload).status_code == 422
    for suffix in ("/confirm", ""):
        method = client.post if suffix else client.patch
        assert method(path + suffix, json={"paid_date": (today_in_lima() + timedelta(days=1)).isoformat()}).status_code == 422
        assert method(path + suffix, json={"paid_date": "2025-01-01", "amount": "1"}).status_code == 422
    assert client.patch(path, json={"paid_date": None}).status_code == 422
    other = create(client)
    wrong = f"/debts/{other['debt_id']}/installments/{debt['installments'][0]['installment_id']}"
    assert client.post(wrong + "/confirm", json={}).status_code == 404
    missing = f"/debts/{uuid4()}"
    assert client.get(missing).status_code == 404
    assert client.patch(missing, json={"name": "New"}).status_code == 404
    assert client.get(missing + "/installments").status_code == 404
    assert client.get("/debts/invalid").status_code == 422
    assert client.get(base).json() == debt


def test_creation_and_schedule_replacement_rollback_on_insert_failure(debts):
    client, _, engine, _ = debts
    debt = create(client)
    base = f"/debts/{debt['debt_id']}"

    def fail_installment(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO debt_installments"):
            raise IntegrityError(statement, parameters, RuntimeError("simulated insert failure"))

    event.listen(engine, "before_cursor_execute", fail_installment)
    try:
        response = client.post("/debts", json={
            "name": "Broken", "creditor": "Person", "installment_amount": "20",
            "total_installments": 1, "first_due_date": "2025-01-01",
        })
        assert response.status_code == 500
        assert response.json() == {"detail": "No se pudo acceder a las deudas."}
        assert client.patch(base, json={"installment_amount": "999"}).status_code == 500
    finally:
        event.remove(engine, "before_cursor_execute", fail_installment)
    assert client.get("/debts").json() == [debt]
    assert client.get(base).json() == debt


@pytest.mark.parametrize("operation", ["confirm", "undo", "schedule_vs_confirm"])
def test_concurrent_writes_preserve_one_payment_and_calendar(debts, operation):
    _, repository, _, _ = debts
    debt = DebtService(repository).create(DebtCreate(
        name="Loan", creditor="Person", installment_amount=Decimal("10"), total_installments=2,
        first_due_date=date(2025, 1, 31),
    ))
    uid, iid = str(debt.debt_id), str(debt.installments[0].installment_id)
    if operation == "undo":
        repository.confirm_payment(uid, iid, DebtPaymentConfirmation())
    barrier = Barrier(2)

    def run(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            if operation == "schedule_vs_confirm" and index == 0:
                repository.update(uid, DebtUpdate(installment_amount=Decimal("20")))
            elif operation == "undo":
                repository.undo_payment(uid, iid)
            else:
                repository.confirm_payment(uid, iid, DebtPaymentConfirmation())
            return "ok"
        except (DebtConflictError, DebtNotFoundError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(run, range(2)))
    assert sorted(outcomes) == ["conflict", "ok"]
    final = repository.get(uid)
    assert len(final.installments) == 2
    if operation == "schedule_vs_confirm":
        assert (final.paid_installments, final.remaining_balance) in [
            (0, Decimal("40.00")), (1, Decimal("10.00")),
        ]
    else:
        assert final.paid_installments == (1 if operation == "confirm" else 0)


def test_migration_reverts_only_debts(debts):
    _, _, engine, config = debts
    command.downgrade(config, "7b21c9d840ef")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT name FROM utilities WHERE utility_id='old'")) == "Luz"
    command.upgrade(config, "head")
    command.check(config)


def test_every_route_rejects_missing_token_and_accepts_signed_token(debts, monkeypatch):
    client, _, _, _ = debts
    monkeypatch.delitem(app.dependency_overrides, get_current_user, raising=False)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    issuer = "https://issuer.example.test/realms/subscriptions"
    for key, value in {
        "KEYCLOAK_PUBLIC_URL": "https://issuer.example.test", "KEYCLOAK_REALM": "subscriptions",
        "KEYCLOAK_WEB_CLIENT_ID": "subscriptions-web", "KEYCLOAK_ISSUER_URL": issuer,
        "KEYCLOAK_JWKS_URL": issuer + "/certs", "KEYCLOAK_API_AUDIENCE": "subscriptions-api",
    }.items():
        monkeypatch.setenv(key, value)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "_get_jwks_client", lambda _: SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key()),
    ))
    now = int(time.time())
    token = jwt.encode({"iss": issuer, "sub": "debt-user", "aud": "subscriptions-api",
                        "iat": now, "exp": now + 300}, private, algorithm="RS256")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": "Loan", "creditor": "Person", "installment_amount": "10",
               "total_installments": 1, "first_due_date": "2025-01-01"}
    response = client.post("/debts", headers=headers, json=payload)
    assert response.status_code == 201
    debt = response.json()
    base = f"/debts/{debt['debt_id']}"
    path = base + "/installments/" + debt["installments"][0]["installment_id"]
    for method, url, body in [
        ("GET", "/debts", None), ("POST", "/debts", payload),
        ("GET", "/debts/summary?year=2025&month=1", None),
        ("GET", base, None), ("PATCH", base, {"name": "New"}),
        ("GET", base + "/installments", None),
        ("POST", path + "/confirm", {}), ("PATCH", path, {"paid_date": "2025-01-01"}),
        ("POST", path + "/undo", None),
    ]:
        rejected = client.request(method, url, json=body)
        assert rejected.status_code == 401
        assert rejected.headers["www-authenticate"] == "Bearer"
    assert client.get("/debts", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.post(path + "/confirm", headers=headers, json={}).status_code == 200
    assert client.patch(path, headers=headers, json={"paid_date": "2025-01-01"}).status_code == 200
    assert client.patch(base, headers=headers, json={"is_active": False}).status_code == 200
    assert client.get(base, headers=headers).json()["paid_installments"] == 1
    assert client.get(base + "/installments", headers=headers).json()[0]["status"] == "paid"
    assert client.get("/debts/summary?year=2025&month=1", headers=headers).json()["total_paid"] == "10.00"
    assert client.post(path + "/undo", headers=headers).status_code == 200


def test_unmigrated_database_returns_public_error(debts, tmp_path):
    client, _, _, _ = debts
    missing = make_engine(f"sqlite:///{tmp_path / 'missing.db'}")
    app.dependency_overrides[get_service] = lambda: DebtService(DebtRepository(missing))
    try:
        response = client.get("/debts")
        assert response.status_code == 500
        assert response.json() == {"detail": "No se pudo acceder a las deudas."}
    finally:
        missing.dispose()

"""Creation of already-paid subscriptions must preserve dates and be atomic."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.db_models import RenewalRecord
from app.main import app
from app.routers import subscriptions
from app.services.subscription_service import SubscriptionService
from app.utils.dates import today_in_lima
from tests.helpers import temporary_repository


@pytest.fixture
def paid_api(monkeypatch):
    with temporary_repository() as repository:
        monkeypatch.setattr(subscriptions, "_service", SubscriptionService(repository))
        with TestClient(app) as client:
            yield client, repository


def payload(**changes):
    return {
        "name": "Música", "cost": "20.00", "billing_cycle": "monthly",
        "renewal_date": "2025-01-31", "initial_payment": {
            "paid_date": "2025-01-30", "paid_amount": "19.90",
        }, **changes,
    }


def test_creates_history_advances_once_preserves_anchor_and_supports_undo(paid_api):
    client, _ = paid_api
    created = client.post("/subscriptions", json=payload())
    assert created.status_code == 201
    subscription = created.json()
    assert subscription["renewal_date"] == "2025-02-28"
    assert Decimal(subscription["cost"]) == Decimal("20.00")
    path = f"/subscriptions/{subscription['subscription_id']}/renewals"
    history = client.get(path).json()
    assert len(history) == 1
    assert history[0]["scheduled_date"] == "2025-01-31"
    assert history[0]["paid_date"] == "2025-01-30"
    assert Decimal(history[0]["paid_amount"]) == Decimal("19.90")
    assert client.post(path, json={"scheduled_date": "2025-02-28"}).status_code == 201
    assert client.get("/subscriptions").json()[0]["renewal_date"] == "2025-03-31"
    assert client.post(path + "/undo").json()["renewal_date"] == "2025-02-28"
    assert client.post(path + "/undo").json()["renewal_date"] == "2025-01-31"
    assert client.get(path).json() == []


def test_current_month_paid_subscription_defaults_actual_date_and_amount(paid_api):
    client, _ = paid_api
    today = today_in_lima()
    created = client.post("/subscriptions", json=payload(renewal_date=today.isoformat(), initial_payment={}))
    assert created.status_code == 201
    subscription = created.json()
    assert date.fromisoformat(subscription["renewal_date"]) > today
    history = client.get(f"/subscriptions/{subscription['subscription_id']}/renewals").json()
    assert history[0]["paid_date"] == today.isoformat()
    assert Decimal(history[0]["paid_amount"]) == Decimal("20.00")


def test_yearly_leap_day_and_inactive_history_are_preserved(paid_api):
    client, _ = paid_api
    created = client.post("/subscriptions", json=payload(
        billing_cycle="yearly", renewal_date="2024-02-29", is_active=False,
        initial_payment={"paid_date": "2024-03-01"},
    ))
    assert created.status_code == 201
    assert created.json()["renewal_date"] == "2025-02-28"
    assert created.json()["is_active"] is False
    assert client.get("/subscriptions/summary").json()["total_monthly_cost"] == "0.00"
    history = client.get(f"/subscriptions/{created.json()['subscription_id']}/renewals").json()
    assert history[0]["scheduled_date"] == "2024-02-29"
    assert history[0]["paid_date"] == "2024-03-01"


def test_future_billing_date_can_be_paid_in_advance(paid_api):
    client, _ = paid_api
    scheduled = today_in_lima() + timedelta(days=5)
    created = client.post("/subscriptions", json=payload(renewal_date=scheduled.isoformat(), initial_payment={}))
    assert created.status_code == 201
    history = client.get(f"/subscriptions/{created.json()['subscription_id']}/renewals").json()
    assert history[0]["scheduled_date"] == scheduled.isoformat()
    assert history[0]["paid_date"] == today_in_lima().isoformat()


@pytest.mark.parametrize("changes", [
    {"initial_payment": None},
    {"initial_payment": {"paid_date": "2999-01-01"}},
    {"initial_payment": {"paid_amount": "0"}},
    {"initial_payment": {"paid_amount": "1.001"}},
    {"initial_payment": {"paid_amount": "10000000"}},
    {"renewal_date": "9999-12-31", "initial_payment": {}},
])
def test_invalid_initial_payments_leave_no_subscription(paid_api, changes):
    client, _ = paid_api
    response = client.post("/subscriptions", json=payload(**changes))
    assert response.status_code == 422
    assert client.get("/subscriptions").json() == []


def test_pending_creation_remains_future_only_without_history(paid_api):
    client, _ = paid_api
    data = payload(renewal_date=(today_in_lima() + timedelta(days=5)).isoformat())
    del data["initial_payment"]
    created = client.post("/subscriptions", json=data)
    assert created.status_code == 201
    assert created.json()["renewal_date"] == data["renewal_date"]
    assert client.get(f"/subscriptions/{created.json()['subscription_id']}/renewals").json() == []
    data["renewal_date"] = today_in_lima().isoformat()
    assert client.post("/subscriptions", json=data).status_code == 422


def test_failed_history_insert_rolls_back_subscription_too(paid_api):
    client, repository = paid_api

    def fail_history(*_args):
        raise IntegrityError("INSERT renewals", {}, RuntimeError("Simulated failure"))

    event.listen(RenewalRecord, "before_insert", fail_history)
    try:
        response = client.post("/subscriptions", json=payload())
        assert response.status_code == 500
        assert response.json() == {"detail": "No se pudo guardar la suscripción y su pago."}
    finally:
        event.remove(RenewalRecord, "before_insert", fail_history)
    assert repository.list_all() == []

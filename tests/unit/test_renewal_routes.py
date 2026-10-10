from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.subscription import BillingCycle, Subscription
from app.routers.subscriptions import set_service
from app.services.renewal_calculator import calculate_next_renewal_date
from app.services.subscription_service import SubscriptionService
from app.utils.dates import today_in_lima
from tests.helpers import temporary_repository


@pytest.fixture()
def api_context():
    with temporary_repository() as repository:
        service = SubscriptionService(repository)
        set_service(service)
        yield repository, TestClient(app)


def _create_subscription(client: TestClient, *, future_days: int = 20) -> dict:
    response = client.post(
        "/subscriptions",
        json={
            "name": "Music",
            "cost": "12.50",
            "billing_cycle": "monthly",
            "renewal_date": (today_in_lima() + timedelta(days=future_days)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_history_endpoint_returns_created_payments_latest_first(api_context):
    _, client = api_context
    subscription = _create_subscription(client)
    subscription_id = subscription["subscription_id"]
    scheduled_date = date.fromisoformat(subscription["renewal_date"])

    first_payment = client.post(
        f"/subscriptions/{subscription_id}/renewals",
        json={"scheduled_date": scheduled_date.isoformat()},
    )
    assert first_payment.status_code == 201

    next_date = calculate_next_renewal_date(
        scheduled_date, BillingCycle.monthly, scheduled_date.day
    )

    second_payment = client.post(
        f"/subscriptions/{subscription_id}/renewals",
        json={"scheduled_date": next_date.isoformat(), "paid_amount": "13.75"},
    )
    assert second_payment.status_code == 201

    history = client.get(f"/subscriptions/{subscription_id}/renewals")
    assert history.status_code == 200
    assert [entry["renewal_id"] for entry in history.json()] == [
        second_payment.json()["renewal_id"],
        first_payment.json()["renewal_id"],
    ]
    assert history.json()[0]["paid_amount"] == "13.75"


def test_confirmation_defaults_payment_fields_and_rejects_stale_retry(api_context):
    _, client = api_context
    subscription = _create_subscription(client)
    path = f"/subscriptions/{subscription['subscription_id']}/renewals"
    payload = {"scheduled_date": subscription["renewal_date"]}
    assert client.get(path).json() == []

    response = client.post(path, json=payload)
    assert response.status_code == 201
    assert response.json()["scheduled_date"] == subscription["renewal_date"]
    assert response.json()["paid_date"] == today_in_lima().isoformat()
    assert Decimal(response.json()["paid_amount"]) == Decimal("12.50")

    retry = client.post(path, json=payload)
    assert retry.status_code == 409
    assert retry.json() == {"detail": "The pending renewal date has changed"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"scheduled_date": "2030-01-01", "paid_amount": "0"},
        {"scheduled_date": "2030-01-01", "paid_amount": "1.001"},
        {"scheduled_date": "2030-01-01", "paid_date": "2999-01-01"},
    ],
)
def test_confirmation_validates_required_and_invalid_payment_fields(api_context, payload):
    _, client = api_context
    subscription = _create_subscription(client)

    response = client.post(
        f"/subscriptions/{subscription['subscription_id']}/renewals", json=payload
    )

    assert response.status_code == 422


def test_history_and_confirmation_return_404_for_missing_subscription(api_context):
    _, client = api_context
    missing_id = str(uuid4())

    history = client.get(f"/subscriptions/{missing_id}/renewals")
    confirmation = client.post(
        f"/subscriptions/{missing_id}/renewals",
        json={"scheduled_date": "2030-01-01"},
    )

    assert history.status_code == 404
    assert confirmation.status_code == 404
    assert history.json() == {"detail": "Subscription not found"}

    undo = client.post(f"/subscriptions/{missing_id}/renewals/undo")
    assert undo.status_code == 404


def test_renewal_routes_reject_invalid_subscription_uuid(api_context):
    _, client = api_context

    history = client.get("/subscriptions/not-a-uuid/renewals")
    confirmation = client.post(
        "/subscriptions/not-a-uuid/renewals",
        json={"scheduled_date": "2030-01-01"},
    )

    assert history.status_code == 422
    assert confirmation.status_code == 422


def test_undo_endpoint_restores_schedule_and_clears_latest_history(api_context):
    _, client = api_context
    subscription = _create_subscription(client)
    subscription_id = subscription["subscription_id"]
    renewals_url = f"/subscriptions/{subscription_id}/renewals"
    scheduled_date = subscription["renewal_date"]
    confirmed = client.post(renewals_url, json={"scheduled_date": scheduled_date})
    assert confirmed.status_code == 201

    undone = client.post(f"{renewals_url}/undo")
    assert undone.status_code == 200
    assert undone.json()["renewal_date"] == scheduled_date
    assert client.get(renewals_url).json() == []


def test_undo_endpoint_reports_conflict_without_history_or_after_schedule_edit(api_context):
    _, client = api_context
    subscription = _create_subscription(client)
    subscription_id = subscription["subscription_id"]
    renewals_url = f"/subscriptions/{subscription_id}/renewals"

    no_history = client.post(f"{renewals_url}/undo")
    assert no_history.status_code == 409

    confirmed = client.post(
        renewals_url, json={"scheduled_date": subscription["renewal_date"]}
    )
    assert confirmed.status_code == 201
    changed_date = (today_in_lima() + timedelta(days=180)).isoformat()
    changed = client.put(
        f"/subscriptions/{subscription_id}", json={"renewal_date": changed_date}
    )
    assert changed.status_code == 200

    blocked_undo = client.post(f"{renewals_url}/undo")
    assert blocked_undo.status_code == 409


def test_deleting_subscription_makes_renewal_history_unavailable(api_context):
    _, client = api_context
    subscription = _create_subscription(client)
    subscription_id = subscription["subscription_id"]
    client.post(
        f"/subscriptions/{subscription_id}/renewals",
        json={"scheduled_date": subscription["renewal_date"]},
    )

    deleted = client.delete(f"/subscriptions/{subscription_id}")

    assert deleted.status_code == 204
    assert client.get(f"/subscriptions/{subscription_id}/renewals").status_code == 404


def test_existing_crud_and_summary_endpoints_use_the_same_persistent_store(api_context):
    _, client = api_context
    created = _create_subscription(client)
    subscription_id = created["subscription_id"]

    listed = client.get("/subscriptions")
    summary_before = client.get("/subscriptions/summary")
    updated = client.put(
        f"/subscriptions/{subscription_id}", json={"cost": "18.25"}
    )
    summary_after = client.get("/subscriptions/summary")

    assert listed.status_code == 200
    assert listed.json()[0]["subscription_id"] == subscription_id
    assert Decimal(summary_before.json()["total_monthly_cost"]) == Decimal("12.50")
    assert updated.status_code == 200
    assert Decimal(summary_after.json()["total_monthly_cost"]) == Decimal("18.25")


def test_alerts_include_past_due_items_and_use_lima_today(api_context, monkeypatch):
    repository, client = api_context
    lima_today = date(2026, 5, 10)
    monkeypatch.setattr("app.services.subscription_service.today_in_lima", lambda: lima_today)
    overdue = Subscription(
        subscription_id=uuid4(),
        name="Overdue",
        cost=Decimal("8.00"),
        billing_cycle=BillingCycle.monthly,
        renewal_date=lima_today - timedelta(days=400),
        is_active=True,
    )
    upcoming = Subscription(
        subscription_id=uuid4(),
        name="Upcoming",
        cost=Decimal("15.00"),
        billing_cycle=BillingCycle.monthly,
        renewal_date=lima_today + timedelta(days=7),
        is_active=True,
    )
    inactive_overdue = Subscription(
        subscription_id=uuid4(),
        name="Inactive overdue",
        cost=Decimal("5.00"),
        billing_cycle=BillingCycle.yearly,
        renewal_date=lima_today - timedelta(days=1),
        is_active=False,
    )
    for subscription in (upcoming, inactive_overdue, overdue):
        repository.add(subscription)

    response = client.get("/subscriptions/alerts")

    assert response.status_code == 200
    assert [(item["name"], item["days_until_renewal"]) for item in response.json()] == [
        ("Overdue", -400),
        ("Upcoming", 7),
    ]


def test_openapi_documents_renewal_routes_and_conflict_responses(api_context):
    _, client = api_context
    openapi = client.get("/openapi.json").json()

    assert "/subscriptions/{subscription_id}/renewals" in openapi["paths"]
    assert "/subscriptions/{subscription_id}/renewals/undo" in openapi["paths"]
    assert "409" in openapi["paths"]["/subscriptions/{subscription_id}/renewals"]["post"]["responses"]
    assert "RenewalEntry" in openapi["components"]["schemas"]

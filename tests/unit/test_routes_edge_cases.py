"""
Edge case tests for FastAPI subscription endpoints.

Covers:
- POST /subscriptions: missing required fields → 422
- GET /subscriptions: empty store → []
- DELETE /subscriptions/{id}: non-existent ID → 404
- PUT /subscriptions/{id}: non-existent ID → 404, empty body → 422
- GET /subscriptions/alerts: no subscriptions in window → []
- Store unavailable → 500

Requirements: 1.3, 1.4, 1.8, 2.2, 3.2, 3.5, 4.2, 6.6, 5.5, 6.9
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.subscriptions import set_service
from app.services.subscription_service import SubscriptionService
from tests.helpers import temporary_repository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def configure_repository():
    """Give each route test an isolated in-memory SQLite database."""
    with temporary_repository() as repository:
        set_service(SubscriptionService(repository))
        yield repository


@pytest.fixture()
def client():
    return TestClient(app)


# A minimal valid payload — used as the baseline for missing-field tests.
def _valid_payload(*, future_days: int = 30) -> dict:
    renewal = (date.today() + timedelta(days=future_days)).isoformat()
    return {
        "name": "Netflix",
        "cost": "9.99",
        "billing_cycle": "monthly",
        "renewal_date": renewal,
    }


# ---------------------------------------------------------------------------
# 1. POST /subscriptions — missing required fields → 422
# ---------------------------------------------------------------------------

def test_post_missing_name_returns_422(client):
    """Requirement 1.3 — name is required."""
    payload = _valid_payload()
    del payload["name"]
    response = client.post("/subscriptions", json=payload)
    assert response.status_code == 422


def test_post_missing_cost_returns_422(client):
    """Requirement 1.4 — cost is required."""
    payload = _valid_payload()
    del payload["cost"]
    response = client.post("/subscriptions", json=payload)
    assert response.status_code == 422


def test_post_missing_renewal_date_returns_422(client):
    """Requirement 1.8 — renewal_date is required."""
    payload = _valid_payload()
    del payload["renewal_date"]
    response = client.post("/subscriptions", json=payload)
    assert response.status_code == 422


def test_post_blank_name_returns_422(client):
    payload = _valid_payload()
    payload["name"] = "   "
    response = client.post("/subscriptions", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 2. GET /subscriptions — empty store → []
# ---------------------------------------------------------------------------

def test_get_subscriptions_empty_returns_empty_list(client):
    """Requirement 2.2 — list is empty when no subscriptions exist."""
    response = client.get("/subscriptions")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 3. DELETE /subscriptions/{id} — non-existent ID → 404
# ---------------------------------------------------------------------------

def test_delete_nonexistent_subscription_returns_404(client):
    """Requirement 4.2 — deleting a subscription that does not exist returns 404."""
    non_existent_id = "00000000-0000-4000-8000-000000000000"
    response = client.delete(f"/subscriptions/{non_existent_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 4. PUT /subscriptions/{id} — non-existent ID → 404
# ---------------------------------------------------------------------------

def test_put_nonexistent_subscription_returns_404(client):
    """Requirement 3.2 — updating a subscription that does not exist returns 404."""
    non_existent_id = "00000000-0000-4000-8000-000000000000"
    renewal = (date.today() + timedelta(days=10)).isoformat()
    response = client.put(
        f"/subscriptions/{non_existent_id}",
        json={"name": "Updated Name", "renewal_date": renewal},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 5. PUT /subscriptions/{id} — empty body → 422
# ---------------------------------------------------------------------------

def test_put_empty_body_returns_422(client):
    """Requirement 3.5 — PUT with no fields provided returns 422."""
    # First create a subscription so we have a valid ID.
    payload = _valid_payload()
    create_response = client.post("/subscriptions", json=payload)
    assert create_response.status_code == 201
    subscription_id = create_response.json()["subscription_id"]

    response = client.put(f"/subscriptions/{subscription_id}", json={})
    assert response.status_code == 422


def test_put_only_null_fields_returns_422(client):
    created = client.post("/subscriptions", json=_valid_payload())
    assert created.status_code == 201
    subscription_id = created.json()["subscription_id"]

    response = client.put(f"/subscriptions/{subscription_id}", json={"name": None})
    assert response.status_code == 422


def test_put_reactivation_requires_reviewed_renewal_date(client):
    payload = {**_valid_payload(), "is_active": False}
    created = client.post("/subscriptions", json=payload)
    assert created.status_code == 201
    subscription_id = created.json()["subscription_id"]

    without_review = client.put(
        f"/subscriptions/{subscription_id}", json={"is_active": True}
    )
    assert without_review.status_code == 422

    reviewed_date = (date.today() + timedelta(days=45)).isoformat()
    with_review = client.put(
        f"/subscriptions/{subscription_id}",
        json={"is_active": True, "renewal_date": reviewed_date},
    )
    assert with_review.status_code == 200
    assert with_review.json()["renewal_date"] == reviewed_date


# ---------------------------------------------------------------------------
# 6. GET /subscriptions/alerts — no subscriptions in window → []
# ---------------------------------------------------------------------------

def test_get_alerts_no_subscriptions_in_window_returns_empty_list(client):
    """Requirement 6.6 — alerts list is empty when no subscriptions fall within the window."""
    response = client.get("/subscriptions/alerts")
    assert response.status_code == 200
    assert response.json() == []


def test_get_alerts_subscription_outside_window_returns_empty_list(client):
    """Requirement 6.6 — subscription with renewal far in the future is not in the alert window."""
    # monthly window is 7 days; renewal in 60 days → outside window
    payload = _valid_payload(future_days=60)
    create_response = client.post("/subscriptions", json=payload)
    assert create_response.status_code == 201

    response = client.get("/subscriptions/alerts")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 7. Store unavailable → 500
# ---------------------------------------------------------------------------

def test_get_subscriptions_database_unavailable_returns_500(client, configure_repository):
    """When the database engine is unavailable, the API returns 500."""
    configure_repository._engine = None
    response = client.get("/subscriptions")
    assert response.status_code == 500

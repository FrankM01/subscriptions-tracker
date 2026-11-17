"""Monthly totals distinguish recorded obligations from actual payments."""

import pytest

from app.auth import get_current_user
from app.main import app
from tests.unit.test_utility_catalog import catalog, create_utility  # noqa: F401
from tests.unit.test_utility_payments import create_entry


def summary(client, year=2025, month=11):
    response = client.get("/utilities/summary", params={"year": year, "month": month})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_month_returns_decimal_zeroes(catalog):
    client, _ = catalog
    assert summary(client) == {
        "year": 2025, "month": 11, "pending_count": 0, "paid_count": 0,
        "total_pending": "0.00", "total_paid": "0.00",
    }


def test_monthly_totals_use_period_and_include_archived_services(catalog):
    client, _ = catalog
    first = create_utility(client)["utility_id"]
    second = create_utility(client, "Agua")["utility_id"]
    archived = create_utility(client, "Internet")["utility_id"]
    create_entry(client, first, amount="0.10")
    create_entry(client, second, amount="0.20")
    create_entry(client, archived, amount="50.35", paid_date="2025-12-02")
    create_entry(client, first, year=2024, amount="900")
    create_entry(client, first, month=12, amount="700", paid_date="2025-11-30")
    assert client.patch(f"/utilities/{archived}", json={"is_active": False}).status_code == 200
    assert client.patch(f"/utilities/{second}", json={"is_active": False}).status_code == 200
    assert summary(client) == {
        "year": 2025, "month": 11, "pending_count": 2, "paid_count": 1,
        "total_pending": "0.30", "total_paid": "50.35",
    }
    assert summary(client, month=12)["total_paid"] == "700.00"
    assert summary(client, year=2024)["total_pending"] == "900.00"


def test_summary_tracks_corrections_confirmation_undo_and_period_moves(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid, amount="12.34")
    path = f"/utilities/{uid}/entries/{entry['entry_id']}"
    assert summary(client)["total_pending"] == "12.34"
    assert client.post(path + "/confirm", json={"amount": "13.45"}).status_code == 200
    paid = summary(client)
    assert (paid["pending_count"], paid["paid_count"], paid["total_pending"], paid["total_paid"]) == (0, 1, "0.00", "13.45")
    assert client.patch(path, json={"amount": "14.56"}).status_code == 200
    assert summary(client)["total_paid"] == "14.56"
    assert client.post(path + "/undo").status_code == 200
    assert summary(client)["total_pending"] == "14.56"
    assert summary(client)["paid_count"] == 0
    assert client.patch(path, json={"month": 12}).status_code == 200
    assert summary(client)["pending_count"] == 0
    assert summary(client, month=12)["total_pending"] == "14.56"


@pytest.mark.parametrize("params", [
    {}, {"year": 2025}, {"month": 11}, {"year": 1899, "month": 11},
    {"year": 10000, "month": 11}, {"year": 2025, "month": 0},
    {"year": 2025, "month": 13}, {"year": "invalid", "month": 11},
])
def test_summary_requires_valid_year_and_month(catalog, params):
    client, _ = catalog
    assert client.get("/utilities/summary", params=params).status_code == 422


def test_summary_requires_authentication(catalog, monkeypatch):
    client, _ = catalog
    monkeypatch.delitem(app.dependency_overrides, get_current_user)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    assert client.get("/utilities/summary?year=2025&month=11").status_code == 401

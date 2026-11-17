"""Monthly contributions and atomic payment workflows."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest

from app.auth import get_current_user
from app.main import app
from app.models.utility import UtilityEntryCreate, UtilityPaymentConfirmation
from app.repositories.utility_repository import UtilityEntryConflictError, UtilityRepository
from app.utils.dates import today_in_lima
from tests.unit.test_utility_catalog import catalog, create_utility  # noqa: F401


def create_entry(client, utility_id, **overrides):
    response = client.post(f"/utilities/{utility_id}/entries", json={
        "year": 2025, "month": 11, "amount": "45.10", **overrides,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_pending_confirm_correct_undo_and_reconfirm(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid, due_date="2025-11-30", notes="Mi aporte")
    path = f"/utilities/{uid}/entries/{entry['entry_id']}"
    assert entry["status"] == "pending"
    corrected = client.patch(path, json={"amount": "47.25", "due_date": None, "notes": None})
    assert corrected.status_code == 200
    assert corrected.json()["due_date"] is None
    assert corrected.json()["notes"] is None
    confirmed = client.post(path + "/confirm", json={})
    assert confirmed.status_code == 200
    assert confirmed.json()["amount"] == "47.25"
    assert confirmed.json()["paid_date"] == today_in_lima().isoformat()
    assert confirmed.json()["status"] == "paid"
    assert client.post(path + "/confirm", json={"amount": "100"}).status_code == 409
    assert client.get(f"/utilities/{uid}/entries").json() == [confirmed.json()]
    corrected = client.patch(path, json={"paid_date": "2025-12-02", "amount": "46.30"})
    assert corrected.status_code == 200
    assert corrected.json()["month"] == 11
    assert corrected.json()["paid_date"] == "2025-12-02"
    undone = client.post(path + "/undo")
    assert undone.status_code == 200
    assert undone.json()["paid_date"] is None
    assert undone.json()["status"] == "pending"
    assert undone.json()["amount"] == "46.30"
    assert client.post(path + "/undo").status_code == 409
    paid = client.post(path + "/confirm", json={"amount": "49.99", "paid_date": "2025-12-03"})
    assert paid.status_code == 200
    assert paid.json()["amount"] == "49.99"
    assert paid.json()["year"] == 2025
    assert paid.json()["month"] == 11


def test_direct_historical_payment_duplicate_period_and_correction_rollback(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    first = create_entry(client, uid, paid_date="2025-12-02")
    second = create_entry(client, uid, month=12)
    assert first["status"] == "paid"
    path = f"/utilities/{uid}/entries"
    assert client.post(path, json={"year": 2025, "month": 11, "amount": "20"}).status_code == 409
    response = client.patch(path + f"/{second['entry_id']}", json={"month": 11, "amount": "999"})
    assert response.status_code == 409
    assert client.get(path).json() == [second, first]
    moved = client.patch(path + f"/{second['entry_id']}", json={"year": 2026, "month": 1})
    assert moved.status_code == 200
    assert moved.json()["year"] == 2026
    assert moved.json()["amount"] == "45.10"
    other = create_utility(client, "Agua")["utility_id"]
    assert create_entry(client, other)["month"] == 11


def test_archive_blocks_new_periods_but_allows_settling_and_correcting_existing_ones(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid)
    base = f"/utilities/{uid}"
    assert client.patch(base, json={"is_active": False}).status_code == 200
    assert client.post(base + "/entries", json={"year": 2025, "month": 12, "amount": "40"}).status_code == 409
    path = base + f"/entries/{entry['entry_id']}"
    assert client.patch(path, json={"notes": "Corrección"}).status_code == 200
    assert client.post(path + "/confirm", json={}).status_code == 200
    assert client.post(path + "/undo").status_code == 200
    assert client.patch(base, json={"is_active": True}).status_code == 200
    assert create_entry(client, uid, month=12)["status"] == "pending"


@pytest.mark.parametrize("operation,payload", [
    ("create", {"amount": "0"}), ("create", {"amount": "1.001"}),
    ("create", {"month": 13}), ("create", {"year": 10000}),
    ("create", {"paid_date": "2999-01-01"}),
    ("update", {}), ("update", {"amount": None}),
    ("update", {"paid_date": None}), ("update", {"month": None}),
    ("update", {"year": None}), ("update", {"amount": "-1"}),
    ("update", {"paid_date": "2999-01-01"}),
    ("confirm", {"amount": "0"}), ("confirm", {"amount": "1.001"}),
    ("confirm", {"paid_date": "2999-01-01"}), ("confirm", {"unknown": True}),
])
def test_invalid_commands_do_not_modify_entry(catalog, operation, payload):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid)
    base = f"/utilities/{uid}/entries"
    path = base + f"/{entry['entry_id']}"
    if operation == "create":
        response = client.post(base, json={"year": 2025, "month": 12, "amount": "40", **payload})
    elif operation == "update":
        response = client.patch(path, json=payload)
    else:
        response = client.post(path + "/confirm", json=payload)
    assert response.status_code == 422
    assert client.get(base).json() == [entry]


def test_patch_cannot_bypass_payment_confirmation(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid)
    path = f"/utilities/{uid}/entries/{entry['entry_id']}"
    assert client.patch(path, json={"paid_date": "2025-12-01"}).status_code == 409
    assert client.get(f"/utilities/{uid}/entries").json() == [entry]


def test_wrong_parent_or_missing_entry_never_modifies_another_service(catalog):
    client, _ = catalog
    uid = create_utility(client)["utility_id"]
    other = create_utility(client, "Gas")["utility_id"]
    entry = create_entry(client, uid)
    for parent, eid in [(other, entry["entry_id"]), (uid, str(uuid4())), (str(uuid4()), entry["entry_id"])]:
        path = f"/utilities/{parent}/entries/{eid}"
        for response in (
            client.patch(path, json={"amount": "10"}),
            client.post(path + "/confirm", json={}), client.post(path + "/undo"),
        ):
            assert response.status_code == 404
    assert client.post(f"/utilities/{uuid4()}/entries", json={"year": 2025, "month": 11, "amount": "20"}).status_code == 404
    assert client.get(f"/utilities/{uid}/entries").json() == [entry]


@pytest.mark.parametrize("method,suffix,payload", [
    ("POST", "", {"year": 2025, "month": 11, "amount": "20"}),
    ("PATCH", "/entry", {"amount": "10"}),
    ("POST", "/entry/confirm", {}), ("POST", "/entry/undo", None),
])
def test_monthly_write_routes_require_authentication(catalog, monkeypatch, method, suffix, payload):
    client, _ = catalog
    monkeypatch.delitem(app.dependency_overrides, get_current_user)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    path = f"/utilities/{uuid4()}/entries" + suffix.replace("entry", str(uuid4()))
    response = client.request(method, path, json=payload)
    assert response.status_code == 401


@pytest.mark.parametrize("operation", ["create", "confirm", "undo"])
def test_simultaneous_commands_have_one_success_and_one_conflict(catalog, operation):
    client, engine = catalog
    uid = create_utility(client)["utility_id"]
    entry = None
    if operation != "create":
        entry = create_entry(client, uid, paid_date="2025-12-01" if operation == "undo" else None)
    barrier = Barrier(2)

    def run():
        repository = UtilityRepository(engine)
        barrier.wait(timeout=5)
        try:
            if operation == "create":
                result = repository.create_entry(uid, UtilityEntryCreate(year=2025, month=11, amount="45.10"))
            elif operation == "confirm":
                result = repository.confirm_payment(uid, entry["entry_id"], UtilityPaymentConfirmation())
            else:
                result = repository.undo_payment(uid, entry["entry_id"])
            return result.status
        except UtilityEntryConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    expected = "paid" if operation == "confirm" else "pending"
    assert sorted(results) == sorted([expected, "conflict"])
    history = client.get(f"/utilities/{uid}/entries").json()
    assert len(history) == 1
    assert history[0]["status"] == expected


def test_payment_persists_after_reconnecting_database(catalog):
    client, engine = catalog
    uid = create_utility(client)["utility_id"]
    entry = create_entry(client, uid)
    path = f"/utilities/{uid}/entries/{entry['entry_id']}/confirm"
    assert client.post(path, json={"amount": "50.20", "paid_date": "2025-12-02"}).status_code == 200
    engine.dispose()
    stored = UtilityRepository(engine).list_entries(uid)[0]
    assert str(stored.amount) == "50.20"
    assert stored.paid_date == date(2025, 12, 2)
    assert stored.month == 11

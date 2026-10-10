# Feature: subscriptions-tracker, Property 6: Cada suscripción en la lista contiene exactamente los campos requeridos
# Validates: Requirements 2.3

from decimal import Decimal
from datetime import date, timedelta

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from fastapi.testclient import TestClient

from app.main import app
from app.routers.subscriptions import set_service
from app.services.subscription_service import SubscriptionService
from app.store.subscription_store import SubscriptionStore


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_cost = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
).filter(lambda x: not x.is_nan() and not x.is_infinite())

billing_cycle_strategy = st.sampled_from(["monthly", "yearly"])

future_date = st.dates(
    min_value=date.today() + timedelta(days=1),
    max_value=date(2030, 12, 31),
)

valid_subscription_strategy = st.fixed_dictionaries({
    "name": st.text(min_size=1, max_size=100),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.booleans(),
})

REQUIRED_FIELDS = {"subscription_id", "name", "cost", "billing_cycle", "renewal_date", "is_active"}


# ---------------------------------------------------------------------------
# Property 6
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(payloads=st.lists(valid_subscription_strategy, min_size=1, max_size=10))
def test_list_response_contains_required_fields(payloads: list[dict]):
    """
    **Validates: Requirements 2.3**

    Property 6: For any set of subscriptions stored in the system, GET /subscriptions
    SHALL return for each subscription exactly the fields: subscription_id, name, cost,
    billing_cycle, renewal_date, and is_active — with no extra or missing fields —
    matching the originally created/updated data.
    """
    # Fresh isolated store and service for each test run
    store = SubscriptionStore()
    service = SubscriptionService(store=store)
    set_service(service)

    client = TestClient(app)

    # POST each subscription and track created data by subscription_id
    created: dict[str, dict] = {}
    for payload in payloads:
        response = client.post("/subscriptions", json={
            **payload,
            "cost": str(payload["cost"]),  # serialize Decimal as string for JSON
        })
        assert response.status_code == 201, f"Expected 201 but got {response.status_code}: {response.text}"
        body = response.json()
        created[body["subscription_id"]] = payload

    # GET /subscriptions
    list_response = client.get("/subscriptions")
    assert list_response.status_code == 200, (
        f"Expected 200 but got {list_response.status_code}: {list_response.text}"
    )

    items = list_response.json()

    # Each item must have exactly the required fields — no more, no less
    for item in items:
        actual_keys = set(item.keys())
        assert actual_keys == REQUIRED_FIELDS, (
            f"Item has unexpected fields. "
            f"Extra: {actual_keys - REQUIRED_FIELDS}, "
            f"Missing: {REQUIRED_FIELDS - actual_keys}. "
            f"Item: {item}"
        )

    # Values for created subscriptions must match the original payload
    items_by_id = {item["subscription_id"]: item for item in items}
    for sub_id, original_payload in created.items():
        assert sub_id in items_by_id, f"Created subscription {sub_id} not found in GET /subscriptions response"
        item = items_by_id[sub_id]

        assert item["name"] == original_payload["name"], (
            f"name mismatch for {sub_id}: expected {original_payload['name']!r}, got {item['name']!r}"
        )
        assert Decimal(str(item["cost"])) == Decimal(str(original_payload["cost"])), (
            f"cost mismatch for {sub_id}: expected {original_payload['cost']}, got {item['cost']}"
        )
        assert item["billing_cycle"] == original_payload["billing_cycle"], (
            f"billing_cycle mismatch for {sub_id}: expected {original_payload['billing_cycle']!r}, "
            f"got {item['billing_cycle']!r}"
        )
        assert item["renewal_date"] == original_payload["renewal_date"], (
            f"renewal_date mismatch for {sub_id}: expected {original_payload['renewal_date']!r}, "
            f"got {item['renewal_date']!r}"
        )
        assert item["is_active"] == original_payload["is_active"], (
            f"is_active mismatch for {sub_id}: expected {original_payload['is_active']!r}, "
            f"got {item['is_active']!r}"
        )

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
from tests.helpers import temporary_repository, valid_name_strategy


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
    "name": valid_name_strategy(),
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
    with temporary_repository() as repository:
        set_service(SubscriptionService(repository=repository))
        client = TestClient(app)

        created: dict[str, dict] = {}
        for payload in payloads:
            response = client.post("/subscriptions", json={
                **payload,
                "cost": str(payload["cost"]),
            })
            assert response.status_code == 201, (
                f"Expected 201 but got {response.status_code}: {response.text}"
            )
            body = response.json()
            created[body["subscription_id"]] = payload

        list_response = client.get("/subscriptions")
        assert list_response.status_code == 200, (
            f"Expected 200 but got {list_response.status_code}: {list_response.text}"
        )

        items = list_response.json()
        for item in items:
            actual_keys = set(item.keys())
            assert actual_keys == REQUIRED_FIELDS, (
                f"Item has unexpected fields. "
                f"Extra: {actual_keys - REQUIRED_FIELDS}, "
                f"Missing: {REQUIRED_FIELDS - actual_keys}. Item: {item}"
            )

        items_by_id = {item["subscription_id"]: item for item in items}
        for sub_id, original_payload in created.items():
            assert sub_id in items_by_id
            item = items_by_id[sub_id]
            assert item["name"] == original_payload["name"]
            assert Decimal(str(item["cost"])) == Decimal(str(original_payload["cost"]))
            assert item["billing_cycle"] == original_payload["billing_cycle"]
            assert item["renewal_date"] == original_payload["renewal_date"]
            assert item["is_active"] == original_payload["is_active"]

# Feature: subscriptions-tracker, Property 8: Una suscripción eliminada no vuelve a aparecer en ningún endpoint posterior
# Validates: Requirements 4.1, 4.3

from decimal import Decimal
from datetime import date, timedelta

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from fastapi.testclient import TestClient

from app.main import app, store
from app.routers.subscriptions import set_service
from app.services.subscription_service import SubscriptionService


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

# Always use is_active=True so the subscription contributes to total_monthly_cost,
# making the summary check unambiguous regardless of billing_cycle.
valid_subscription_strategy = st.fixed_dictionaries({
    "name": st.text(min_size=1, max_size=100),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.just(True),
})


def _monthly_contribution(cost: Decimal, billing_cycle: str) -> Decimal:
    """Compute the monthly cost contribution of a single active subscription."""
    if billing_cycle == "monthly":
        return cost
    return round(cost / Decimal("12"), 2)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_store():
    """Reset the shared in-memory store before and after each test for isolation."""
    store._store = {}
    set_service(SubscriptionService(store))
    yield
    store._store = {}


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Property 8
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(payload=valid_subscription_strategy)
def test_deleted_subscription_not_visible(payload: dict):
    """
    **Validates: Requirements 4.1, 4.3**

    Property 8: For any subscription created and then successfully deleted (DELETE → 204),
    the deleted subscription SHALL:
      (a) not appear in GET /subscriptions response, and
      (b) not contribute to total_monthly_cost in GET /subscriptions/summary.
    Both conditions must hold atomically in the same delete operation.
    """
    # Reset state for each Hypothesis example (autouse fixture resets per test
    # function invocation, not per Hypothesis example — reset here explicitly).
    store._store = {}
    set_service(SubscriptionService(store))

    client = TestClient(app)

    # Step 1: Create the subscription (is_active=True, so it contributes to summary).
    create_response = client.post("/subscriptions", json={
        **payload,
        "cost": str(payload["cost"]),  # serialize Decimal as string for JSON
    })
    assert create_response.status_code == 201, (
        f"Expected 201 on creation, got {create_response.status_code}: {create_response.text}"
    )
    created = create_response.json()
    subscription_id = created["subscription_id"]

    # Step 2: Record the summary BEFORE deletion.
    summary_before = client.get("/subscriptions/summary")
    assert summary_before.status_code == 200
    cost_before = Decimal(str(summary_before.json()["total_monthly_cost"]))

    # Compute the expected monthly contribution of the subscription we will delete.
    contribution = _monthly_contribution(payload["cost"], payload["billing_cycle"])

    # Step 3: Delete the subscription.
    delete_response = client.delete(f"/subscriptions/{subscription_id}")
    assert delete_response.status_code == 204, (
        f"Expected 204 on deletion, got {delete_response.status_code}: {delete_response.text}"
    )

    # Step 4 (a): Assert the deleted subscription does NOT appear in GET /subscriptions.
    list_response = client.get("/subscriptions")
    assert list_response.status_code == 200
    subscriptions_after = list_response.json()
    ids_after = [s["subscription_id"] for s in subscriptions_after]
    assert subscription_id not in ids_after, (
        f"Deleted subscription {subscription_id} still appears in GET /subscriptions"
    )

    # Step 4 (b): Assert the deleted subscription's contribution is removed from summary.
    # The store is empty after deletion (only one subscription was created), so
    # total_monthly_cost must be 0.00.  We also verify it equals cost_before - contribution
    # to confirm the exact amount was deducted atomically.
    summary_after = client.get("/subscriptions/summary")
    assert summary_after.status_code == 200
    cost_after = Decimal(str(summary_after.json()["total_monthly_cost"]))

    expected_cost_after = round(cost_before - contribution, 2)
    assert cost_after == expected_cost_after, (
        f"total_monthly_cost after deletion is incorrect: "
        f"before={cost_before}, contribution={contribution}, "
        f"expected_after={expected_cost_after}, actual_after={cost_after}"
    )

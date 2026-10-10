# Feature: subscriptions-tracker, Property 8: Una suscripción eliminada no vuelve a aparecer en ningún endpoint posterior
# Validates: Requirements 4.1, 4.3

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

# Always use is_active=True so the subscription contributes to total_monthly_cost,
# making the summary check unambiguous regardless of billing_cycle.
valid_subscription_strategy = st.fixed_dictionaries({
    "name": valid_name_strategy(),
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
    with temporary_repository() as repository:
        set_service(SubscriptionService(repository=repository))
        client = TestClient(app)

        create_response = client.post("/subscriptions", json={
            **payload,
            "cost": str(payload["cost"]),
        })
        assert create_response.status_code == 201, (
            f"Expected 201 on creation, got {create_response.status_code}: {create_response.text}"
        )
        subscription_id = create_response.json()["subscription_id"]

        summary_before = client.get("/subscriptions/summary")
        assert summary_before.status_code == 200
        cost_before = Decimal(str(summary_before.json()["total_monthly_cost"]))
        contribution = _monthly_contribution(payload["cost"], payload["billing_cycle"])

        delete_response = client.delete(f"/subscriptions/{subscription_id}")
        assert delete_response.status_code == 204

        list_response = client.get("/subscriptions")
        assert list_response.status_code == 200
        ids_after = [item["subscription_id"] for item in list_response.json()]
        assert subscription_id not in ids_after

        summary_after = client.get("/subscriptions/summary")
        assert summary_after.status_code == 200
        cost_after = Decimal(str(summary_after.json()["total_monthly_cost"]))
        assert cost_after == round(cost_before - contribution, 2)

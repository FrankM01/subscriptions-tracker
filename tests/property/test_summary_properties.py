# Feature: subscriptions-tracker, Property 9: El cálculo de gasto mensual total es correcto para cualquier mezcla de suscripciones
# Validates: Requirements 5.1, 5.2, 5.4

from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.subscription import BillingCycle, Subscription
from app.services.cost_calculator import CostCalculator


valid_cost = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
)

billing_cycle_strategy = st.sampled_from([BillingCycle.monthly, BillingCycle.yearly])

subscription_strategy = st.builds(
    Subscription,
    subscription_id=st.uuids(),
    name=st.text(min_size=1),
    cost=valid_cost,
    billing_cycle=billing_cycle_strategy,
    renewal_date=st.dates(
        min_value=date.today() + timedelta(days=1),
        max_value=date.today() + timedelta(days=3650),
    ),
    is_active=st.booleans(),
)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(subscriptions=st.lists(subscription_strategy, min_size=0, max_size=20))
def test_summary_monthly_cost_calculation(subscriptions: list[Subscription]):
    """
    **Validates: Requirements 5.1, 5.2, 5.4**

    Property 9: For any mix of subscriptions, total_monthly_cost equals the sum of
    monthly costs for all active subscriptions, rounded to 2 decimals.
    Inactive subscriptions must not contribute to the total.
    """
    # Compute expected total manually
    expected = Decimal("0")
    for sub in subscriptions:
        if sub.is_active:
            if sub.billing_cycle == BillingCycle.monthly:
                expected += sub.cost
            else:  # yearly
                expected += round(sub.cost / Decimal("12"), 2)
    expected = round(expected, 2)

    result = CostCalculator.total_monthly_cost(subscriptions)

    assert result == expected

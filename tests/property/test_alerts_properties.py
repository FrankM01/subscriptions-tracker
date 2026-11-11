# Feature: subscriptions-tracker, Property 10: Las alertas retornadas contienen suscripciones activas vencidas o dentro de su ventana
# Validates: Requirements 6.1, 6.3, 6.4, 6.7

from datetime import date
from decimal import Decimal

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.subscription import BillingCycle, Subscription
from app.services.alert_engine import AlertEngine, ALERT_WINDOW


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
    renewal_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2050, 12, 31)),
    is_active=st.booleans(),
)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    today=st.dates(),
    subscriptions=st.lists(subscription_strategy, min_size=0, max_size=20),
)
def test_alerts_contain_correct_subscriptions(today: date, subscriptions: list[Subscription]):
    """
    **Validates: Requirements 6.1, 6.3, 6.4, 6.7**

    Property 10: For any list of subscriptions and any reference date `today`,
    AlertEngine.evaluate() must return exactly those subscriptions that are:
      - active (is_active == True)
      - overdue (days_until_renewal < 0), or
      - within the alert window for their billing cycle:
          * monthly: 0 <= days_until_renewal <= 7
          * yearly:  0 <= days_until_renewal <= 30
    """
    # Manually compute expected set of subscription_ids
    expected_ids = set()
    for sub in subscriptions:
        if not sub.is_active:
            continue
        days = (sub.renewal_date - today).days
        window = ALERT_WINDOW[sub.billing_cycle]
        if days < 0 or days <= window:
            expected_ids.add(sub.subscription_id)

    alerts = AlertEngine.evaluate(subscriptions, today)
    actual_ids = {alert.subscription_id for alert in alerts}

    assert actual_ids == expected_ids


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    today=st.dates(),
    subscriptions=st.lists(subscription_strategy, min_size=0, max_size=20),
)
def test_days_until_renewal_is_floor_of_calendar_days(today: date, subscriptions: list[Subscription]):
    """
    **Validates: Requirements 6.5**

    Property 11: For every RenewalAlert returned by AlertEngine.evaluate(),
    the `days_until_renewal` field must equal exactly the floor of calendar day
    difference between `today` and `renewal_date`, i.e.:
        alert.days_until_renewal == (alert.renewal_date - today).days
    """
    alerts = AlertEngine.evaluate(subscriptions, today)
    for alert in alerts:
        expected_days = (alert.renewal_date - today).days
        assert alert.days_until_renewal == expected_days, (
            f"Expected days_until_renewal={expected_days} for subscription "
            f"{alert.subscription_id} (renewal_date={alert.renewal_date}, today={today}), "
            f"but got {alert.days_until_renewal}"
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    today=st.dates(),
    subscriptions=st.lists(subscription_strategy, min_size=0, max_size=20),
)
def test_alerts_sorted_ascending_by_days_until_renewal(today: date, subscriptions: list[Subscription]):
    """
    **Validates: Requirements 6.8**

    Property 12: For any list of subscriptions and any reference date `today`,
    the list returned by AlertEngine.evaluate() must be sorted in ascending order
    by `days_until_renewal`, i.e. subscriptions with the soonest renewal appear first.

    For every consecutive pair of alerts in the result:
        alerts[i].days_until_renewal <= alerts[i+1].days_until_renewal
    """
    alerts = AlertEngine.evaluate(subscriptions, today)
    for i in range(len(alerts) - 1):
        assert alerts[i].days_until_renewal <= alerts[i + 1].days_until_renewal, (
            f"Alerts not sorted ascending at index {i}: "
            f"alerts[{i}].days_until_renewal={alerts[i].days_until_renewal} > "
            f"alerts[{i+1}].days_until_renewal={alerts[i+1].days_until_renewal}"
        )

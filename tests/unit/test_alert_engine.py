"""Unit tests for AlertEngine — Requirements 6.1, 6.3, 6.4, 6.5, 6.7, 6.8."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.subscription import BillingCycle, Subscription
from app.services.alert_engine import ALERT_WINDOW, AlertEngine


def make_subscription(**kwargs) -> Subscription:
    """Helper to build a valid Subscription instance."""
    defaults = {
        "subscription_id": uuid4(),
        "name": "Netflix",
        "cost": Decimal("9.99"),
        "billing_cycle": BillingCycle.monthly,
        "renewal_date": date.today() + timedelta(days=5),
        "is_active": True,
    }
    defaults.update(kwargs)
    return Subscription(**defaults)


TODAY = date(2024, 6, 15)


# ---------------------------------------------------------------------------
# days_until_renewal — Req 6.5: floor of calendar days
# ---------------------------------------------------------------------------

def test_days_until_renewal_same_day_returns_zero():
    """Req 6.5 — when renewal_date equals today, days_until_renewal is 0."""
    result = AlertEngine.days_until_renewal(TODAY, TODAY)

    assert result == 0


def test_days_until_renewal_future_date_returns_correct_days():
    """Req 6.5 — days_until_renewal is the floor of calendar days between today and renewal_date."""
    renewal = TODAY + timedelta(days=5)

    result = AlertEngine.days_until_renewal(renewal, TODAY)

    assert result == 5


def test_days_until_renewal_past_date_returns_negative():
    """Req 6.5 — a past renewal_date yields a negative value (past due)."""
    renewal = TODAY - timedelta(days=3)

    result = AlertEngine.days_until_renewal(renewal, TODAY)

    assert result == -3


# ---------------------------------------------------------------------------
# evaluate — Req 6.1 & 6.3: monthly subscription within window (0 days)
# ---------------------------------------------------------------------------

def test_evaluate_monthly_subscription_renewing_today_is_included():
    """Req 6.1, 6.3 — monthly sub renewing today (0 days) is within the 7-day window."""
    sub = make_subscription(
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY,
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 1
    assert alerts[0].subscription_id == sub.subscription_id
    assert alerts[0].days_until_renewal == 0


def test_evaluate_monthly_subscription_within_window_is_included():
    """Req 6.1, 6.3 — monthly sub with renewal within 7-day window is included."""
    sub = make_subscription(
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=7),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 1
    assert alerts[0].days_until_renewal == 7


def test_evaluate_yearly_subscription_within_30_day_window_is_included():
    """Req 6.1, 6.4 — yearly sub with renewal within 30-day window is included."""
    sub = make_subscription(
        billing_cycle=BillingCycle.yearly,
        renewal_date=TODAY + timedelta(days=30),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 1
    assert alerts[0].days_until_renewal == 30


# ---------------------------------------------------------------------------
# evaluate — Req 6.3 & 6.4: subscriptions outside their alert window are excluded
# ---------------------------------------------------------------------------

def test_evaluate_monthly_subscription_outside_window_is_excluded():
    """Req 6.3 — monthly sub renewing in 8 days (> 7-day window) is not included."""
    sub = make_subscription(
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=8),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 0


def test_evaluate_yearly_subscription_outside_window_is_excluded():
    """Req 6.4 — yearly sub renewing in 31 days (> 30-day window) is not included."""
    sub = make_subscription(
        billing_cycle=BillingCycle.yearly,
        renewal_date=TODAY + timedelta(days=31),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 0


def test_evaluate_subscription_with_past_renewal_date_is_included():
    """Overdue active subscriptions remain visible until confirmed or corrected."""
    sub = make_subscription(
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY - timedelta(days=1),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 1
    assert alerts[0].days_until_renewal == -1


# ---------------------------------------------------------------------------
# evaluate — Req 6.7: inactive subscriptions are excluded
# ---------------------------------------------------------------------------

def test_evaluate_inactive_subscription_within_window_is_excluded():
    """Req 6.7 — inactive sub renewing within window is not included."""
    sub = make_subscription(
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=3),
        is_active=False,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 0


def test_evaluate_mixed_active_inactive_returns_only_active():
    """Req 6.1, 6.7 — only active subs within window appear in alerts."""
    active_sub = make_subscription(
        name="Active",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=3),
        is_active=True,
    )
    inactive_sub = make_subscription(
        name="Inactive",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=3),
        is_active=False,
    )

    alerts = AlertEngine.evaluate([active_sub, inactive_sub], TODAY)

    assert len(alerts) == 1
    assert alerts[0].subscription_id == active_sub.subscription_id


# ---------------------------------------------------------------------------
# evaluate — Req 6.1: empty subscription list returns empty alerts
# ---------------------------------------------------------------------------

def test_evaluate_empty_list_returns_empty_alerts():
    """Req 6.1 — no subscriptions → no alerts."""
    alerts = AlertEngine.evaluate([], TODAY)

    assert alerts == []


# ---------------------------------------------------------------------------
# evaluate — Req 6.8: alerts are sorted ascending by days_until_renewal
# ---------------------------------------------------------------------------

def test_evaluate_alerts_sorted_ascending_by_days_until_renewal():
    """Req 6.8 — returned alerts are sorted soonest-first."""
    sub_3_days = make_subscription(
        name="Three days",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=3),
        is_active=True,
    )
    sub_1_day = make_subscription(
        name="One day",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=1),
        is_active=True,
    )
    sub_6_days = make_subscription(
        name="Six days",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=6),
        is_active=True,
    )

    # Pass in non-sorted order to confirm the output ordering is applied
    alerts = AlertEngine.evaluate([sub_3_days, sub_1_day, sub_6_days], TODAY)

    assert len(alerts) == 3
    assert alerts[0].days_until_renewal == 1
    assert alerts[1].days_until_renewal == 3
    assert alerts[2].days_until_renewal == 6


def test_evaluate_alerts_sorted_ascending_with_zero_days():
    """Req 6.8 — a same-day renewal sorts before any future renewal."""
    sub_today = make_subscription(
        name="Today",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY,
        is_active=True,
    )
    sub_5_days = make_subscription(
        name="Five days",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=5),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub_5_days, sub_today], TODAY)

    assert alerts[0].days_until_renewal == 0
    assert alerts[1].days_until_renewal == 5


# ---------------------------------------------------------------------------
# evaluate — alert fields are populated correctly (Req 6.5)
# ---------------------------------------------------------------------------

def test_evaluate_alert_contains_correct_fields():
    """Req 6.5 — RenewalAlert fields match the originating subscription."""
    sub = make_subscription(
        name="Spotify",
        billing_cycle=BillingCycle.monthly,
        renewal_date=TODAY + timedelta(days=4),
        is_active=True,
    )

    alerts = AlertEngine.evaluate([sub], TODAY)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.subscription_id == sub.subscription_id
    assert alert.name == sub.name
    assert alert.renewal_date == sub.renewal_date
    assert alert.billing_cycle == sub.billing_cycle
    assert alert.days_until_renewal == 4


# ---------------------------------------------------------------------------
# ALERT_WINDOW constants — sanity check (Req 6.3, 6.4)
# ---------------------------------------------------------------------------

def test_alert_window_monthly_is_7_days():
    """Req 6.3 — monthly alert window is 7 days."""
    assert ALERT_WINDOW[BillingCycle.monthly] == 7


def test_alert_window_yearly_is_30_days():
    """Req 6.4 — yearly alert window is 30 days."""
    assert ALERT_WINDOW[BillingCycle.yearly] == 30

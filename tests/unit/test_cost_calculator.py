"""Unit tests for CostCalculator — Requirements 5.1, 5.2, 5.3, 5.4."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.subscription import BillingCycle, Subscription
from app.services.cost_calculator import CostCalculator


def make_subscription(**kwargs) -> Subscription:
    """Helper to build a valid Subscription instance."""
    defaults = {
        "subscription_id": uuid4(),
        "name": "Netflix",
        "cost": Decimal("9.99"),
        "billing_cycle": BillingCycle.monthly,
        "renewal_date": date.today() + timedelta(days=30),
        "is_active": True,
    }
    defaults.update(kwargs)
    return Subscription(**defaults)


# ---------------------------------------------------------------------------
# monthly_cost — Req 5.4: monthly billing → cost returned directly
# ---------------------------------------------------------------------------

def test_monthly_cost_for_monthly_subscription_returns_cost_directly():
    """Req 5.4 — monthly billing_cycle cost is summed directly without normalisation."""
    sub = make_subscription(cost=Decimal("15.99"), billing_cycle=BillingCycle.monthly)

    result = CostCalculator.monthly_cost(sub)

    assert result == Decimal("15.99")


def test_monthly_cost_for_monthly_subscription_exact_value():
    """Req 5.4 — another monthly subscription with a round cost."""
    sub = make_subscription(cost=Decimal("10.00"), billing_cycle=BillingCycle.monthly)

    result = CostCalculator.monthly_cost(sub)

    assert result == Decimal("10.00")


# ---------------------------------------------------------------------------
# monthly_cost — Req 5.2: yearly billing → cost divided by 12
# ---------------------------------------------------------------------------

def test_monthly_cost_for_yearly_subscription_divides_by_12():
    """Req 5.2 — yearly billing_cycle cost is divided by 12."""
    sub = make_subscription(cost=Decimal("120.00"), billing_cycle=BillingCycle.yearly)

    result = CostCalculator.monthly_cost(sub)

    assert result == Decimal("10.00")


def test_monthly_cost_for_yearly_subscription_rounds_to_2_decimals():
    """Req 5.2 — division result is rounded to 2 decimal places."""
    sub = make_subscription(cost=Decimal("99.99"), billing_cycle=BillingCycle.yearly)

    result = CostCalculator.monthly_cost(sub)

    assert result == round(Decimal("99.99") / Decimal("12"), 2)
    assert result == Decimal("8.33")


# ---------------------------------------------------------------------------
# total_monthly_cost — Req 5.1 & 5.2 & 5.4: mixed active subscriptions
# ---------------------------------------------------------------------------

def test_total_monthly_cost_mixed_billing_cycles():
    """Req 5.1, 5.2, 5.4 — total considers monthly directly and yearly / 12."""
    monthly_sub = make_subscription(
        cost=Decimal("10.00"), billing_cycle=BillingCycle.monthly, is_active=True
    )
    yearly_sub = make_subscription(
        cost=Decimal("120.00"), billing_cycle=BillingCycle.yearly, is_active=True
    )

    result = CostCalculator.total_monthly_cost([monthly_sub, yearly_sub])

    # 10.00 + (120.00 / 12) = 10.00 + 10.00 = 20.00
    assert result == Decimal("20.00")


def test_total_monthly_cost_only_monthly_subscriptions():
    """Req 5.1, 5.4 — sum of multiple active monthly subscriptions."""
    sub1 = make_subscription(cost=Decimal("9.99"), billing_cycle=BillingCycle.monthly, is_active=True)
    sub2 = make_subscription(cost=Decimal("4.99"), billing_cycle=BillingCycle.monthly, is_active=True)

    result = CostCalculator.total_monthly_cost([sub1, sub2])

    assert result == Decimal("14.98")


def test_total_monthly_cost_only_yearly_subscriptions():
    """Req 5.1, 5.2 — sum of multiple active yearly subscriptions."""
    sub1 = make_subscription(cost=Decimal("120.00"), billing_cycle=BillingCycle.yearly, is_active=True)
    sub2 = make_subscription(cost=Decimal("240.00"), billing_cycle=BillingCycle.yearly, is_active=True)

    result = CostCalculator.total_monthly_cost([sub1, sub2])

    # (120 / 12) + (240 / 12) = 10 + 20 = 30
    assert result == Decimal("30.00")


# ---------------------------------------------------------------------------
# total_monthly_cost — Req 5.3: inactive subscriptions are excluded
# ---------------------------------------------------------------------------

def test_total_monthly_cost_only_inactive_subscriptions_returns_zero():
    """Req 5.3 — no active subscriptions → total is 0.00."""
    inactive1 = make_subscription(cost=Decimal("9.99"), is_active=False)
    inactive2 = make_subscription(cost=Decimal("49.99"), is_active=False)

    result = CostCalculator.total_monthly_cost([inactive1, inactive2])

    assert result == Decimal("0.00")


def test_total_monthly_cost_empty_list_returns_zero():
    """Req 5.3 — empty subscription list → total is 0.00."""
    result = CostCalculator.total_monthly_cost([])

    assert result == Decimal("0.00")


def test_total_monthly_cost_excludes_inactive_from_mixed_list():
    """Req 5.1, 5.3 — inactive subscriptions are not counted in the total."""
    active_sub = make_subscription(
        cost=Decimal("10.00"), billing_cycle=BillingCycle.monthly, is_active=True
    )
    inactive_sub = make_subscription(
        cost=Decimal("100.00"), billing_cycle=BillingCycle.monthly, is_active=False
    )

    result = CostCalculator.total_monthly_cost([active_sub, inactive_sub])

    # Only active_sub counts
    assert result == Decimal("10.00")


# ---------------------------------------------------------------------------
# total_monthly_cost — result is rounded to 2 decimals (Req 5.1)
# ---------------------------------------------------------------------------

def test_total_monthly_cost_result_rounded_to_2_decimals():
    """Req 5.1 — total is rounded to 2 decimal places."""
    sub = make_subscription(
        cost=Decimal("10.00"), billing_cycle=BillingCycle.yearly, is_active=True
    )

    result = CostCalculator.total_monthly_cost([sub])

    # 10.00 / 12 ≈ 0.8333... → rounded to 0.83
    assert result == Decimal("0.83")
    # Ensure it's exactly 2 decimal places
    assert result == round(Decimal("10.00") / Decimal("12"), 2)

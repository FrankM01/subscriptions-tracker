from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.subscription import BillingCycle, SubscriptionCreate, SubscriptionUpdate
from app.utils.dates import today_in_lima


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_subscription_create_rejects_blank_name(name: str):
    with pytest.raises(ValidationError, match="name must not be blank"):
        SubscriptionCreate(
            name=name,
            cost=Decimal("5.00"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=today_in_lima() + timedelta(days=1),
        )


@pytest.mark.parametrize("name", ["", "   "])
def test_subscription_update_rejects_blank_name(name: str):
    with pytest.raises(ValidationError, match="name must not be blank"):
        SubscriptionUpdate(name=name)


@pytest.mark.parametrize("data", [{}, {"name": None}, {"name": None, "cost": None}])
def test_subscription_update_requires_at_least_one_non_null_field(data: dict):
    with pytest.raises(ValidationError, match="non-null field"):
        SubscriptionUpdate(**data)


@pytest.mark.parametrize("cost", [Decimal("0"), Decimal("-0.01")])
def test_subscription_cost_must_be_positive(cost: Decimal):
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Music",
            cost=cost,
            billing_cycle=BillingCycle.monthly,
            renewal_date=today_in_lima() + timedelta(days=1),
        )
    with pytest.raises(ValidationError):
        SubscriptionUpdate(cost=cost)


def test_subscription_cost_must_match_cent_precision():
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Music",
            cost=Decimal("1.001"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=today_in_lima() + timedelta(days=1),
        )
    with pytest.raises(ValidationError):
        SubscriptionUpdate(cost=Decimal("1.001"))


@pytest.mark.parametrize(
    "renewal_date", [today_in_lima(), today_in_lima() - timedelta(days=1)]
)
def test_subscription_renewal_date_must_be_future(renewal_date):
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Music",
            cost=Decimal("5.00"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=renewal_date,
        )
    with pytest.raises(ValidationError):
        SubscriptionUpdate(renewal_date=renewal_date)

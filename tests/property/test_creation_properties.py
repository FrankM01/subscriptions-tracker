# Feature: subscriptions-tracker, Property 3: Cualquier valor de cost menor o igual a cero es rechazado con HTTP 422
# Validates: Requirements 1.5, 3.3

from decimal import Decimal
from datetime import date, timedelta

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.subscription import SubscriptionCreate, SubscriptionUpdate, BillingCycle


invalid_cost = st.one_of(
    st.decimals(max_value=Decimal("0.00"), places=2).filter(lambda x: not x.is_nan() and not x.is_infinite()),
    st.just(Decimal("0"))
)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(cost=invalid_cost)
def test_invalid_cost_rejected_on_create(cost):
    """Property 3: cost <= 0 is rejected by SubscriptionCreate with ValidationError."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Test",
            cost=cost,
            billing_cycle=BillingCycle.monthly,
            renewal_date=tomorrow,
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(cost=invalid_cost)
def test_invalid_cost_rejected_on_update(cost):
    """Property 3: cost <= 0 is rejected by SubscriptionUpdate with ValidationError."""
    with pytest.raises(ValidationError):
        SubscriptionUpdate(cost=cost)


# Feature: subscriptions-tracker, Property 4: Cualquier valor de billing_cycle distinto de los permitidos es rechazado con HTTP 422
# Validates: Requirements 1.6, 3.4

invalid_billing_cycle = st.text().filter(lambda s: s not in ("monthly", "yearly"))


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(billing_cycle=invalid_billing_cycle)
def test_invalid_billing_cycle_rejected_on_create(billing_cycle):
    """Property 4: billing_cycle with invalid value is rejected by SubscriptionCreate with ValidationError."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Test",
            cost=Decimal("9.99"),
            billing_cycle=billing_cycle,
            renewal_date=tomorrow,
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(billing_cycle=invalid_billing_cycle)
def test_invalid_billing_cycle_rejected_on_update(billing_cycle):
    """Property 4: billing_cycle with invalid value is rejected by SubscriptionUpdate with ValidationError."""
    with pytest.raises(ValidationError):
        SubscriptionUpdate(billing_cycle=billing_cycle)


# Feature: subscriptions-tracker, Property 5: Cualquier renewal_date inválida o no futura es rechazada con HTTP 422
# Validates: Requirements 1.9, 1.10, 3.6, 3.7

past_or_today_date = st.one_of(
    st.just(date.today()),
    st.dates(max_value=date.today() - timedelta(days=1))
)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(renewal_date=past_or_today_date)
def test_past_or_today_renewal_date_rejected_on_create(renewal_date):
    """Property 5: renewal_date <= today is rejected by SubscriptionCreate with ValidationError."""
    with pytest.raises(ValidationError):
        SubscriptionCreate(
            name="Test",
            cost=Decimal("9.99"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=renewal_date,
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(renewal_date=past_or_today_date)
def test_past_or_today_renewal_date_rejected_on_update(renewal_date):
    """Property 5: renewal_date <= today is rejected by SubscriptionUpdate with ValidationError."""
    with pytest.raises(ValidationError):
        SubscriptionUpdate(renewal_date=renewal_date)


# Feature: subscriptions-tracker, Property 1: Los subscription_id asignados son UUIDs v4 válidos y únicos
# Validates: Requirements 1.2

import uuid

from app.services.subscription_service import SubscriptionService
from tests.helpers import temporary_repository, valid_name_strategy

valid_cost = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999.99"), places=2).filter(
    lambda x: not x.is_nan() and not x.is_infinite()
)
billing_cycle_strategy = st.sampled_from(["monthly", "yearly"])
future_date = st.dates(min_value=date.today() + timedelta(days=1), max_value=date(2030, 12, 31))

valid_subscription_strategy = st.fixed_dictionaries({
    "name": valid_name_strategy(),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.booleans(),
})


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(payloads=st.lists(valid_subscription_strategy, min_size=2, max_size=20))
def test_created_ids_are_unique_uuids(payloads):
    """Property 1: All subscription_id values assigned are valid UUID v4 and unique."""
    with temporary_repository() as repository:
        service = SubscriptionService(repository=repository)

        ids = []
        for payload in payloads:
            sub = service.create(SubscriptionCreate(**payload))
            ids.append(sub.subscription_id)

    # Assert all IDs are valid UUID v4
    for sub_id in ids:
        parsed = uuid.UUID(str(sub_id))
        assert parsed.version == 4, f"Expected UUID v4, got version {parsed.version} for {sub_id}"

    # Assert all IDs are unique (no duplicates)
    assert len(ids) == len(set(str(i) for i in ids)), "Duplicate subscription_id values found"


# Feature: subscriptions-tracker, Property 2: El campo is_active nunca es sobrescrito por el valor por defecto
# Validates: Requirements 1.7

valid_subscription_with_explicit_is_active = st.fixed_dictionaries({
    "name": valid_name_strategy(),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.booleans(),
})


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(payload=valid_subscription_with_explicit_is_active)
def test_is_active_not_overwritten(payload):
    """Property 2: is_active provided explicitly is never overwritten by the default value True."""
    with temporary_repository() as repository:
        service = SubscriptionService(repository=repository)
        subscription = service.create(SubscriptionCreate(**payload))

    assert subscription.is_active == payload["is_active"], (
        f"Expected is_active={payload['is_active']!r} but got {subscription.is_active!r}"
    )

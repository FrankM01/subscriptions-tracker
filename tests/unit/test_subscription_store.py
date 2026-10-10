"""Unit tests for SubscriptionStore — Requirements 2.2, 4.1, 4.2, 4.3."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.subscription import BillingCycle, Subscription, SubscriptionUpdate
from app.store.subscription_store import SubscriptionStore


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
# add + get (retrieval)
# ---------------------------------------------------------------------------

def test_add_and_get_returns_same_subscription():
    store = SubscriptionStore()
    sub = make_subscription()
    store.add(sub)

    result = store.get(str(sub.subscription_id))

    assert result == sub


# ---------------------------------------------------------------------------
# get with non-existent ID
# ---------------------------------------------------------------------------

def test_get_nonexistent_id_returns_none():
    store = SubscriptionStore()

    result = store.get(str(uuid4()))

    assert result is None


# ---------------------------------------------------------------------------
# list_all on empty store  — Req 2.2
# ---------------------------------------------------------------------------

def test_list_all_empty_store_returns_empty_list():
    store = SubscriptionStore()

    result = store.list_all()

    assert result == []


def test_list_all_returns_all_added_subscriptions():
    store = SubscriptionStore()
    sub1 = make_subscription(name="Netflix")
    sub2 = make_subscription(name="Spotify")
    store.add(sub1)
    store.add(sub2)

    result = store.list_all()

    assert len(result) == 2
    assert sub1 in result
    assert sub2 in result


# ---------------------------------------------------------------------------
# partial update
# ---------------------------------------------------------------------------

def test_update_partial_changes_only_specified_fields():
    store = SubscriptionStore()
    sub = make_subscription(name="Netflix", cost=Decimal("9.99"), is_active=True)
    store.add(sub)

    update = SubscriptionUpdate(name="Netflix Premium")
    updated = store.update(str(sub.subscription_id), update)

    assert updated is not None
    assert updated.name == "Netflix Premium"
    # unchanged fields
    assert updated.cost == Decimal("9.99")
    assert updated.is_active is True
    assert updated.billing_cycle == sub.billing_cycle
    assert updated.renewal_date == sub.renewal_date


def test_update_nonexistent_id_returns_none():
    store = SubscriptionStore()

    update = SubscriptionUpdate(name="Ghost")
    result = store.update(str(uuid4()), update)

    assert result is None


# ---------------------------------------------------------------------------
# delete — Req 4.1, 4.3
# ---------------------------------------------------------------------------

def test_delete_existing_subscription_returns_true():
    store = SubscriptionStore()
    sub = make_subscription()
    store.add(sub)

    result = store.delete(str(sub.subscription_id))

    assert result is True


def test_deleted_subscription_no_longer_in_store():
    """Req 4.1 / 4.3 — deleted subscription must not appear in subsequent reads."""
    store = SubscriptionStore()
    sub = make_subscription()
    store.add(sub)

    store.delete(str(sub.subscription_id))

    assert store.get(str(sub.subscription_id)) is None
    assert sub not in store.list_all()


# ---------------------------------------------------------------------------
# delete with non-existent ID — Req 4.2
# ---------------------------------------------------------------------------

def test_delete_nonexistent_id_returns_false():
    store = SubscriptionStore()

    result = store.delete(str(uuid4()))

    assert result is False


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

def test_is_available_returns_true_on_normal_store():
    store = SubscriptionStore()

    assert store.is_available() is True

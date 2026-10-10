from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.subscription import BillingCycle, Subscription, SubscriptionUpdate
from tests.helpers import temporary_repository


def make_subscription(**kwargs) -> Subscription:
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


def test_add_and_get_returns_same_subscription():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)

        assert repository.get(str(subscription.subscription_id)) == subscription


def test_list_all_reads_persisted_subscriptions():
    with temporary_repository() as repository:
        first = make_subscription(name="Netflix")
        second = make_subscription(name="Spotify")
        repository.add(first)
        repository.add(second)

        results = repository.list_all()
        assert {item.subscription_id for item in results} == {
            first.subscription_id,
            second.subscription_id,
        }


def test_update_changes_only_provided_fields():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)

        updated = repository.update(
            str(subscription.subscription_id), SubscriptionUpdate(name="Premium")
        )

        assert updated is not None
        assert updated.name == "Premium"
        assert updated.cost == subscription.cost
        assert updated.billing_cycle == subscription.billing_cycle
        assert updated.renewal_date == subscription.renewal_date
        assert updated.is_active is subscription.is_active


def test_update_nonexistent_subscription_returns_none():
    with temporary_repository() as repository:
        assert repository.update(str(uuid4()), SubscriptionUpdate(name="Missing")) is None


def test_changing_renewal_date_updates_anchor_day():
    with temporary_repository() as repository:
        subscription = make_subscription(renewal_date=date(2027, 1, 31))
        repository.add(subscription)

        repository.update(
            str(subscription.subscription_id),
            SubscriptionUpdate(renewal_date=date(2027, 2, 28)),
        )
        with repository._engine.connect() as connection:
            record = connection.exec_driver_sql(
                "SELECT anchor_day FROM subscriptions WHERE subscription_id = ?",
                (str(subscription.subscription_id),),
            ).scalar_one()

        assert record == 28


def test_delete_removes_subscription_and_returns_result():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)

        assert repository.delete(str(subscription.subscription_id)) is True
        assert repository.get(str(subscription.subscription_id)) is None
        assert repository.delete(str(subscription.subscription_id)) is False


def test_is_unavailable_without_an_engine():
    from app.repositories.subscription_repository import SubscriptionRepository

    assert SubscriptionRepository(None).is_available() is False


def test_data_survives_repository_recreation(tmp_path):
    from app.database import Base, make_engine
    from app import db_models  # noqa: F401
    from app.repositories.subscription_repository import SubscriptionRepository

    database_url = f"sqlite:///{tmp_path / 'subscriptions.db'}"
    first_engine = make_engine(database_url)
    Base.metadata.create_all(first_engine)
    subscription = make_subscription(cost=Decimal("14.50"))
    SubscriptionRepository(first_engine).add(subscription)
    first_engine.dispose()

    second_engine = make_engine(database_url)
    try:
        loaded = SubscriptionRepository(second_engine).get(str(subscription.subscription_id))
        assert loaded == subscription
    finally:
        second_engine.dispose()

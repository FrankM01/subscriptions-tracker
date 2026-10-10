from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.database import Base, make_engine
from app import db_models  # noqa: F401 - register ORM metadata
from app.models.subscription import (
    BillingCycle,
    RenewalConfirmation,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
)
from app.repositories.subscription_repository import (
    RenewalConflictError,
    SubscriptionRepository,
)
from app.services.subscription_service import SubscriptionService
from app.utils.dates import today_in_lima
from tests.helpers import temporary_repository


def make_subscription(
    *,
    renewal_date: date = date(2025, 1, 31),
    billing_cycle: BillingCycle = BillingCycle.monthly,
    cost: Decimal = Decimal("12.50"),
    is_active: bool = True,
) -> Subscription:
    return Subscription(
        subscription_id=uuid4(),
        name="Music",
        cost=cost,
        billing_cycle=billing_cycle,
        renewal_date=renewal_date,
        is_active=is_active,
    )


def test_confirmation_records_actual_payment_and_advances_one_period():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)

        entry = repository.confirm_renewal(
            str(subscription.subscription_id),
            scheduled_date=date(2025, 1, 31),
            paid_date=today_in_lima(),
            paid_amount=Decimal("15.75"),
        )

        assert entry.scheduled_date == date(2025, 1, 31)
        assert entry.paid_date == today_in_lima()
        assert entry.paid_amount == Decimal("15.75")
        assert repository.get(str(subscription.subscription_id)).renewal_date == date(2025, 2, 28)
        assert repository.list_renewals(str(subscription.subscription_id)) == [entry]


def test_recorded_payment_amount_does_not_change_with_subscription_price():
    with temporary_repository() as repository:
        service = SubscriptionService(repository)
        subscription = make_subscription(renewal_date=today_in_lima() + timedelta(days=1))
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)
        entry = service.confirm_renewal(
            subscription_id,
            RenewalConfirmation(
                scheduled_date=subscription.renewal_date,
                paid_amount=Decimal("11.25"),
            ),
        )

        service.update(subscription_id, SubscriptionUpdate(cost=Decimal("18.00")))

        assert repository.get(subscription_id).cost == Decimal("18.00")
        assert repository.list_renewals(subscription_id)[0].paid_amount == entry.paid_amount
        assert entry.paid_amount == Decimal("11.25")


def test_late_confirmation_advances_only_one_period_and_restores_anchor_next_month():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)

        repository.confirm_renewal(
            str(subscription.subscription_id), date(2025, 1, 31), today_in_lima()
        )
        repository.confirm_renewal(
            str(subscription.subscription_id), date(2025, 2, 28), today_in_lima()
        )

        assert repository.get(str(subscription.subscription_id)).renewal_date == date(2025, 3, 31)
        assert len(repository.list_renewals(str(subscription.subscription_id))) == 2


def test_yearly_confirmation_preserves_february_29_anchor():
    with temporary_repository() as repository:
        subscription = make_subscription(
            renewal_date=date(2024, 2, 29),
            billing_cycle=BillingCycle.yearly,
        )
        repository.add(subscription)

        repository.confirm_renewal(
            str(subscription.subscription_id), date(2024, 2, 29), today_in_lima()
        )

        assert repository.get(str(subscription.subscription_id)).renewal_date == date(2025, 2, 28)


def test_repeated_confirmation_of_stale_period_is_rejected():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)
        repository.confirm_renewal(subscription_id, date(2025, 1, 31), today_in_lima())

        with pytest.raises(RenewalConflictError, match="pending renewal date has changed"):
            repository.confirm_renewal(subscription_id, date(2025, 1, 31), today_in_lima())

        assert len(repository.list_renewals(subscription_id)) == 1


def test_undo_removes_only_latest_confirmation_and_restores_pending_date():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)
        repository.confirm_renewal(subscription_id, date(2025, 1, 31), today_in_lima())
        repository.confirm_renewal(subscription_id, date(2025, 2, 28), today_in_lima())

        restored = repository.undo_latest_renewal(subscription_id)

        assert restored.renewal_date == date(2025, 2, 28)
        assert [item.scheduled_date for item in repository.list_renewals(subscription_id)] == [
            date(2025, 1, 31)
        ]


def test_undo_is_blocked_if_schedule_changed_after_confirmation():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)
        repository.confirm_renewal(subscription_id, date(2025, 1, 31), today_in_lima())
        repository.update(
            subscription_id,
            SubscriptionUpdate(renewal_date=today_in_lima() + timedelta(days=200)),
        )

        with pytest.raises(RenewalConflictError, match="schedule changed"):
            repository.undo_latest_renewal(subscription_id)

        assert len(repository.list_renewals(subscription_id)) == 1


def test_service_defaults_paid_date_and_amount_and_maps_undo_conflicts():
    with temporary_repository() as repository:
        service = SubscriptionService(repository)
        subscription = make_subscription(renewal_date=today_in_lima() + timedelta(days=20))
        repository.add(subscription)

        entry = service.confirm_renewal(
            str(subscription.subscription_id),
            RenewalConfirmation(scheduled_date=subscription.renewal_date),
        )

        assert entry.paid_date == today_in_lima()
        assert entry.paid_amount == subscription.cost
        service.update(
            str(subscription.subscription_id),
            SubscriptionUpdate(renewal_date=today_in_lima() + timedelta(days=100)),
        )

        with pytest.raises(HTTPException) as error:
            service.undo_latest_renewal(str(subscription.subscription_id))
        assert error.value.status_code == 409


def test_deactivation_preserves_history_and_excludes_subscription_from_totals_and_alerts():
    with temporary_repository() as repository:
        service = SubscriptionService(repository)
        renewal = today_in_lima() + timedelta(days=3)
        subscription = service.create(
            SubscriptionCreate(
                name="Music",
                cost=Decimal("12.50"),
                billing_cycle=BillingCycle.monthly,
                renewal_date=renewal,
            )
        )
        subscription_id = str(subscription.subscription_id)
        service.confirm_renewal(
            subscription_id,
            RenewalConfirmation(scheduled_date=renewal, paid_amount=Decimal("13.25")),
        )

        service.update(subscription_id, SubscriptionUpdate(is_active=False))

        assert service.get_summary().total_monthly_cost == Decimal("0.00")
        assert service.get_alerts() == []
        assert service.list_all()[0].is_active is False
        assert len(repository.list_renewals(subscription_id)) == 1


def test_reactivation_requires_a_future_renewal_date_review():
    with temporary_repository() as repository:
        service = SubscriptionService(repository)
        subscription = make_subscription(is_active=False)
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)

        with pytest.raises(HTTPException) as error:
            service.update(subscription_id, SubscriptionUpdate(is_active=True))
        assert error.value.status_code == 422

        reviewed_date = today_in_lima() + timedelta(days=14)
        reactivated = service.update(
            subscription_id,
            SubscriptionUpdate(is_active=True, renewal_date=reviewed_date),
        )
        assert reactivated.is_active is True
        assert reactivated.renewal_date == reviewed_date


def test_permanent_delete_cascades_to_renewal_history():
    with temporary_repository() as repository:
        subscription = make_subscription()
        repository.add(subscription)
        subscription_id = str(subscription.subscription_id)
        repository.confirm_renewal(subscription_id, date(2025, 1, 31), today_in_lima())

        assert repository.delete(subscription_id) is True
        assert repository.list_renewals(subscription_id) == []


def test_concurrent_confirmation_of_same_period_has_one_winner(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrent.db'}")
    Base.metadata.create_all(engine)
    repository = SubscriptionRepository(engine)
    subscription = make_subscription()
    subscription_id = str(subscription.subscription_id)
    repository.add(subscription)

    def confirm():
        try:
            return repository.confirm_renewal(
                subscription_id, date(2025, 1, 31), today_in_lima()
            )
        except RenewalConflictError as error:
            return error

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: confirm(), range(2)))
        assert sum(not isinstance(result, RenewalConflictError) for result in results) == 1
        assert sum(isinstance(result, RenewalConflictError) for result in results) == 1
        assert len(repository.list_renewals(subscription_id)) == 1
    finally:
        engine.dispose()


def test_renewal_history_survives_engine_recreation(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'history.db'}"
    first_engine = make_engine(database_url)
    Base.metadata.create_all(first_engine)
    subscription = make_subscription()
    subscription_id = str(subscription.subscription_id)
    first_repository = SubscriptionRepository(first_engine)
    first_repository.add(subscription)
    first_repository.confirm_renewal(
        subscription_id,
        date(2025, 1, 31),
        today_in_lima(),
        Decimal("17.20"),
    )
    first_engine.dispose()

    second_engine = make_engine(database_url)
    try:
        second_repository = SubscriptionRepository(second_engine)
        history = second_repository.list_renewals(subscription_id)
        assert len(history) == 1
        assert history[0].scheduled_date == date(2025, 1, 31)
        assert history[0].paid_amount == Decimal("17.20")
        assert second_repository.get(subscription_id).renewal_date == date(2025, 2, 28)
    finally:
        second_engine.dispose()


def test_paid_amount_must_have_cent_precision_and_paid_date_cannot_be_future():
    with pytest.raises(ValueError):
        RenewalConfirmation(
            scheduled_date=date(2025, 1, 31), paid_amount=Decimal("10.001")
        )
    with pytest.raises(ValueError, match="paid_date cannot be in the future"):
        RenewalConfirmation(
            scheduled_date=date(2025, 1, 31),
            paid_date=today_in_lima() + timedelta(days=1),
        )

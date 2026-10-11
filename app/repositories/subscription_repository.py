"""SQLite repository for subscriptions and their renewal history."""

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from collections.abc import Iterator, Mapping
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db_models import RenewalRecord, SubscriptionRecord
from app.models.subscription import (
    BillingCycle,
    RenewalEntry,
    Subscription,
    SubscriptionUpdate,
)
from app.services.renewal_calculator import calculate_next_renewal_date


class SubscriptionNotFoundError(LookupError):
    """Raised when a subscription requested for a domain operation is missing."""


class RenewalConflictError(RuntimeError):
    """Raised when the expected pending period or undo state has changed."""


class SubscriptionRepository:
    """Persist and retrieve subscriptions through a SQLAlchemy engine."""

    def __init__(self, engine: Engine | None) -> None:
        self._engine = engine

    @staticmethod
    def _to_record(subscription: Subscription) -> SubscriptionRecord:
        cents = SubscriptionRepository._to_cents(subscription.cost)
        return SubscriptionRecord(
            subscription_id=str(subscription.subscription_id),
            name=subscription.name,
            cost_cents=cents,
            billing_cycle=subscription.billing_cycle.value,
            renewal_date=subscription.renewal_date,
            anchor_day=subscription.renewal_date.day,
            is_active=subscription.is_active,
        )

    @staticmethod
    def _to_cents(amount: Decimal) -> int:
        cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if cents <= 0:
            raise ValueError("Amount must be at least one cent")
        return int(cents)

    @staticmethod
    def _to_model(record: SubscriptionRecord) -> Subscription:
        return Subscription(
            subscription_id=UUID(record.subscription_id),
            name=record.name,
            cost=Decimal(record.cost_cents) / Decimal(100),
            billing_cycle=BillingCycle(record.billing_cycle),
            renewal_date=record.renewal_date,
            is_active=record.is_active,
        )

    @staticmethod
    def _subscription_from_mapping(record: Mapping) -> Subscription:
        return Subscription(
            subscription_id=UUID(record["subscription_id"]),
            name=record["name"],
            cost=Decimal(record["cost_cents"]) / Decimal(100),
            billing_cycle=BillingCycle(record["billing_cycle"]),
            renewal_date=record["renewal_date"],
            is_active=record["is_active"],
        )

    @staticmethod
    def _renewal_from_mapping(record: Mapping) -> RenewalEntry:
        return RenewalEntry(
            renewal_id=record["renewal_id"],
            subscription_id=UUID(record["subscription_id"]),
            scheduled_date=record["scheduled_date"],
            paid_date=record["paid_date"],
            paid_amount=Decimal(record["paid_amount_cents"]) / Decimal(100),
        )

    @contextmanager
    def _atomic_transaction(self) -> Iterator[Connection]:
        """Use SQLite's write lock or a normal transaction for other engines."""
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        connection = self._engine.connect()
        try:
            if self._engine.dialect.name == "sqlite":
                # Acquire SQLite's write lock before reading to serialize renewal
                # confirmation and undo operations.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                connection.begin()
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def is_available(self) -> bool:
        if self._engine is None:
            return False
        try:
            with self._engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
        except SQLAlchemyError:
            return False
        return True

    def add(self, subscription: Subscription) -> None:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session, session.begin():
            session.add(self._to_record(subscription))

    def get(self, subscription_id: str) -> Optional[Subscription]:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session:
            record = session.get(SubscriptionRecord, subscription_id)
            return self._to_model(record) if record is not None else None

    def list_all(self) -> list[Subscription]:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session:
            records = session.scalars(select(SubscriptionRecord)).all()
            return [self._to_model(record) for record in records]

    def update(
        self, subscription_id: str, data: SubscriptionUpdate
    ) -> Optional[Subscription]:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")

        with Session(self._engine) as session, session.begin():
            record = session.get(SubscriptionRecord, subscription_id)
            if record is None:
                return None

            for field, value in data.model_dump(exclude_unset=True).items():
                if value is None:
                    continue
                if field == "cost":
                    record.cost_cents = self._to_cents(value)
                elif field == "billing_cycle":
                    record.billing_cycle = value.value
                elif field == "renewal_date":
                    record.renewal_date = value
                    record.anchor_day = value.day
                else:
                    setattr(record, field, value)

            session.flush()
            session.refresh(record)
            result = self._to_model(record)

        return result

    def confirm_renewal(
        self,
        subscription_id: str,
        scheduled_date: date,
        paid_date: date,
        paid_amount: Decimal | None = None,
    ) -> RenewalEntry:
        """Record one pending period and advance the schedule atomically."""
        subscriptions = SubscriptionRecord.__table__
        renewals = RenewalRecord.__table__

        with self._atomic_transaction() as connection:
            subscription = connection.execute(
                select(subscriptions).where(
                    subscriptions.c.subscription_id == subscription_id
                ).with_for_update()
            ).mappings().one_or_none()
            if subscription is None:
                raise SubscriptionNotFoundError("Subscription not found")
            if subscription["renewal_date"] != scheduled_date:
                raise RenewalConflictError("The pending renewal date has changed")

            cycle = BillingCycle(subscription["billing_cycle"])
            next_date = calculate_next_renewal_date(
                scheduled_date, cycle, subscription["anchor_day"]
            )
            amount = (
                Decimal(subscription["cost_cents"]) / Decimal(100)
                if paid_amount is None
                else paid_amount
            )
            amount_cents = self._to_cents(amount)

            result = connection.execute(
                insert(renewals).values(
                    subscription_id=subscription_id,
                    scheduled_date=scheduled_date,
                    paid_date=paid_date,
                    paid_amount_cents=amount_cents,
                    resulting_renewal_date=next_date,
                    resulting_billing_cycle=cycle.value,
                    resulting_anchor_day=subscription["anchor_day"],
                )
            )
            update_result = connection.execute(
                update(subscriptions)
                .where(
                    subscriptions.c.subscription_id == subscription_id,
                    subscriptions.c.renewal_date == scheduled_date,
                )
                .values(renewal_date=next_date)
            )
            if update_result.rowcount != 1:
                raise RenewalConflictError("The pending renewal date has changed")

            renewal_id = result.inserted_primary_key[0]
            entry = RenewalEntry(
                renewal_id=renewal_id,
                subscription_id=UUID(subscription_id),
                scheduled_date=scheduled_date,
                paid_date=paid_date,
                paid_amount=Decimal(amount_cents) / Decimal(100),
            )
        return entry

    def list_renewals(self, subscription_id: str) -> list[RenewalEntry]:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        renewals = RenewalRecord.__table__
        with Session(self._engine) as session:
            records = session.execute(
                select(renewals)
                .where(renewals.c.subscription_id == subscription_id)
                .order_by(renewals.c.renewal_id.desc())
            ).mappings()
            return [self._renewal_from_mapping(record) for record in records]

    def undo_latest_renewal(self, subscription_id: str) -> Subscription:
        """Remove the latest confirmation and restore its pending period."""
        subscriptions = SubscriptionRecord.__table__
        renewals = RenewalRecord.__table__

        with self._atomic_transaction() as connection:
            subscription = connection.execute(
                select(subscriptions).where(
                    subscriptions.c.subscription_id == subscription_id
                ).with_for_update()
            ).mappings().one_or_none()
            if subscription is None:
                raise SubscriptionNotFoundError("Subscription not found")

            renewal = connection.execute(
                select(renewals)
                .where(renewals.c.subscription_id == subscription_id)
                .order_by(renewals.c.renewal_id.desc())
                .limit(1)
            ).mappings().one_or_none()
            if renewal is None:
                raise RenewalConflictError("There is no renewal confirmation to undo")

            current_schedule = (
                subscription["renewal_date"],
                subscription["billing_cycle"],
                subscription["anchor_day"],
            )
            confirmed_schedule = (
                renewal["resulting_renewal_date"],
                renewal["resulting_billing_cycle"],
                renewal["resulting_anchor_day"],
            )
            if current_schedule != confirmed_schedule:
                raise RenewalConflictError(
                    "The subscription schedule changed after this confirmation"
                )

            connection.execute(
                update(subscriptions)
                .where(subscriptions.c.subscription_id == subscription_id)
                .values(renewal_date=renewal["scheduled_date"])
            )
            connection.execute(
                delete(renewals).where(renewals.c.renewal_id == renewal["renewal_id"])
            )
            restored = dict(subscription)
            restored["renewal_date"] = renewal["scheduled_date"]
            result = self._subscription_from_mapping(restored)
        return result

    def delete(self, subscription_id: str) -> bool:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session, session.begin():
            record = session.get(SubscriptionRecord, subscription_id)
            if record is None:
                return False
            session.delete(record)
        return True

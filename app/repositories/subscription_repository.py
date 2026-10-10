"""SQLite repository for subscription CRUD operations."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db_models import SubscriptionRecord
from app.models.subscription import (
    BillingCycle,
    Subscription,
    SubscriptionUpdate,
)


class SubscriptionRepository:
    """Persist and retrieve subscriptions through a SQLAlchemy engine."""

    def __init__(self, engine: Engine | None) -> None:
        self._engine = engine

    @staticmethod
    def _to_record(subscription: Subscription) -> SubscriptionRecord:
        cents = int(
            (subscription.cost * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
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
    def _to_model(record: SubscriptionRecord) -> Subscription:
        return Subscription(
            subscription_id=UUID(record.subscription_id),
            name=record.name,
            cost=Decimal(record.cost_cents) / Decimal(100),
            billing_cycle=BillingCycle(record.billing_cycle),
            renewal_date=record.renewal_date,
            is_active=record.is_active,
        )

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
                    record.cost_cents = int(
                        (value * 100).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    )
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

    def delete(self, subscription_id: str) -> bool:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session, session.begin():
            record = session.get(SubscriptionRecord, subscription_id)
            if record is None:
                return False
            session.delete(record)
        return True

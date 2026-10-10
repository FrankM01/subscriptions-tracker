import uuid
from datetime import date

from fastapi import HTTPException

from app.models.subscription import (
    RenewalAlert,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
    SummaryResponse,
)
from app.services.alert_engine import AlertEngine
from app.services.cost_calculator import CostCalculator
from app.store.subscription_store import SubscriptionStore


class SubscriptionService:
    def __init__(self, store: SubscriptionStore) -> None:
        self._store = store

    def _check_availability(self) -> None:
        if not self._store.is_available():
            raise HTTPException(status_code=500, detail="Internal server error")

    def create(self, data: SubscriptionCreate) -> Subscription:
        self._check_availability()
        subscription = Subscription(
            subscription_id=uuid.uuid4(),
            name=data.name,
            cost=data.cost,
            billing_cycle=data.billing_cycle,
            renewal_date=data.renewal_date,
            is_active=data.is_active,
        )
        self._store.add(subscription)
        return subscription

    def list_all(self) -> list[Subscription]:
        self._check_availability()
        return self._store.list_all()

    def update(self, subscription_id: str, data: SubscriptionUpdate) -> Subscription:
        self._check_availability()
        if not data.model_dump(exclude_unset=True):
            raise HTTPException(
                status_code=422,
                detail="At least one field must be provided for update",
            )
        updated = self._store.update(subscription_id, data)
        if updated is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return updated

    def delete(self, subscription_id: str) -> None:
        self._check_availability()
        deleted = self._store.delete(subscription_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Subscription not found")

    def get_summary(self) -> SummaryResponse:
        self._check_availability()
        subscriptions = self._store.list_all()
        total = CostCalculator.total_monthly_cost(subscriptions)
        return SummaryResponse(total_monthly_cost=total)

    def get_alerts(self) -> list[RenewalAlert]:
        self._check_availability()
        subscriptions = self._store.list_all()
        return AlertEngine.evaluate(subscriptions, date.today())

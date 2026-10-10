import uuid
from datetime import date

from fastapi import HTTPException

from app.models.subscription import (
    RenewalConfirmation,
    RenewalEntry,
    RenewalAlert,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
    SummaryResponse,
)
from app.services.alert_engine import AlertEngine
from app.services.cost_calculator import CostCalculator
from app.repositories.subscription_repository import (
    RenewalConflictError,
    SubscriptionNotFoundError,
    SubscriptionRepository,
)
from app.utils.dates import today_in_lima


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository) -> None:
        self._repository = repository

    def _check_availability(self) -> None:
        if not self._repository.is_available():
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
        self._repository.add(subscription)
        return subscription

    def list_all(self) -> list[Subscription]:
        self._check_availability()
        return self._repository.list_all()

    def update(self, subscription_id: str, data: SubscriptionUpdate) -> Subscription:
        self._check_availability()
        fields = data.model_dump(exclude_unset=True)
        if not fields or all(value is None for value in fields.values()):
            raise HTTPException(
                status_code=422,
                detail="At least one non-null field must be provided for update",
            )

        existing = self._repository.get(subscription_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if (
            not existing.is_active
            and fields.get("is_active") is True
            and fields.get("renewal_date") is None
        ):
            raise HTTPException(
                status_code=422,
                detail="renewal_date must be reviewed when reactivating a subscription",
            )

        updated = self._repository.update(subscription_id, data)
        if updated is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return updated

    def delete(self, subscription_id: str) -> None:
        self._check_availability()
        deleted = self._repository.delete(subscription_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Subscription not found")

    def confirm_renewal(
        self, subscription_id: str, data: RenewalConfirmation
    ) -> RenewalEntry:
        self._check_availability()
        try:
            return self._repository.confirm_renewal(
                subscription_id=subscription_id,
                scheduled_date=data.scheduled_date,
                paid_date=data.paid_date or today_in_lima(),
                paid_amount=data.paid_amount,
            )
        except SubscriptionNotFoundError as error:
            raise HTTPException(status_code=404, detail="Subscription not found") from error
        except RenewalConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    def undo_latest_renewal(self, subscription_id: str) -> Subscription:
        self._check_availability()
        try:
            return self._repository.undo_latest_renewal(subscription_id)
        except SubscriptionNotFoundError as error:
            raise HTTPException(status_code=404, detail="Subscription not found") from error
        except RenewalConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    def get_summary(self) -> SummaryResponse:
        self._check_availability()
        subscriptions = self._repository.list_all()
        total = CostCalculator.total_monthly_cost(subscriptions)
        return SummaryResponse(total_monthly_cost=total)

    def get_alerts(self) -> list[RenewalAlert]:
        self._check_availability()
        subscriptions = self._repository.list_all()
        return AlertEngine.evaluate(subscriptions, date.today())

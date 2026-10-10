from uuid import UUID

from fastapi import APIRouter, Response, status

from app.models.subscription import (
    ErrorResponse,
    RenewalAlert,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
    SummaryResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

_service: SubscriptionService = None


def set_service(service: SubscriptionService) -> None:
    global _service
    _service = service


# NOTE: Order is critical — static paths (/summary, /alerts) must come before
# parameterised paths (/{subscription_id}) so FastAPI does not treat the literal
# strings "summary" and "alerts" as UUID path parameters.

@router.get(
    "/summary",
    response_model=SummaryResponse,
    responses={500: {"model": ErrorResponse}},
)
def get_summary() -> SummaryResponse:
    return _service.get_summary()


@router.get(
    "/alerts",
    response_model=list[RenewalAlert],
    responses={500: {"model": ErrorResponse}},
)
def get_alerts() -> list[RenewalAlert]:
    return _service.get_alerts()


@router.post(
    "",
    response_model=Subscription,
    status_code=status.HTTP_201_CREATED,
    responses={500: {"model": ErrorResponse}},
)
def create_subscription(data: SubscriptionCreate) -> Subscription:
    return _service.create(data)


@router.get(
    "",
    response_model=list[Subscription],
    responses={500: {"model": ErrorResponse}},
)
def list_subscriptions() -> list[Subscription]:
    return _service.list_all()


@router.put(
    "/{subscription_id}",
    response_model=Subscription,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def update_subscription(subscription_id: UUID, data: SubscriptionUpdate) -> Subscription:
    return _service.update(str(subscription_id), data)


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def delete_subscription(subscription_id: UUID) -> Response:
    _service.delete(str(subscription_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

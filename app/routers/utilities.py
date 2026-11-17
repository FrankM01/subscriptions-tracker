"""Authenticated personal utility catalog API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.auth import get_current_user
from app.models.subscription import ErrorResponse
from app.models.utility import (
    Utility, UtilityCreate, UtilityEntry, UtilityEntryCreate, UtilityEntryUpdate,
    UtilityPaymentConfirmation, UtilityUpdate,
)
from app.services.utility_service import UtilityService


router = APIRouter(
    prefix="/utilities", tags=["utilities"],
    dependencies=[Depends(get_current_user)],
    responses={500: {"model": ErrorResponse}},
)


def get_service(request: Request) -> UtilityService:
    return request.app.state.utility_service


@router.post("", response_model=Utility, status_code=status.HTTP_201_CREATED)
def create_utility(data: UtilityCreate, service: UtilityService = Depends(get_service)) -> Utility:
    return service.create(data)


@router.get("", response_model=list[Utility])
def list_utilities(
    is_active: bool | None = None,
    service: UtilityService = Depends(get_service),
) -> list[Utility]:
    """List all services by default; optionally filter active or archived ones."""
    return service.list_all(is_active)


@router.get("/{utility_id}", response_model=Utility, responses={404: {"model": ErrorResponse}})
def get_utility(utility_id: UUID, service: UtilityService = Depends(get_service)) -> Utility:
    return service.get(str(utility_id))


@router.patch("/{utility_id}", response_model=Utility, responses={404: {"model": ErrorResponse}})
def update_utility(
    utility_id: UUID, data: UtilityUpdate, service: UtilityService = Depends(get_service),
) -> Utility:
    """Edit metadata or archive/reactivate via is_active, preserving all entries."""
    return service.update(str(utility_id), data)


@router.get(
    "/{utility_id}/entries", response_model=list[UtilityEntry],
    responses={404: {"model": ErrorResponse}},
)
def list_entries(
    utility_id: UUID, service: UtilityService = Depends(get_service),
) -> list[UtilityEntry]:
    """History newest period first, including archived services and pending entries."""
    return service.list_entries(str(utility_id))


ENTRY_ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}


@router.post(
    "/{utility_id}/entries", response_model=UtilityEntry,
    status_code=status.HTTP_201_CREATED, responses=ENTRY_ERRORS,
)
def create_entry(
    utility_id: UUID, data: UtilityEntryCreate,
    service: UtilityService = Depends(get_service),
) -> UtilityEntry:
    return service.create_entry(str(utility_id), data)


@router.patch(
    "/{utility_id}/entries/{entry_id}", response_model=UtilityEntry, responses=ENTRY_ERRORS,
)
def update_entry(
    utility_id: UUID, entry_id: UUID, data: UtilityEntryUpdate,
    service: UtilityService = Depends(get_service),
) -> UtilityEntry:
    return service.update_entry(str(utility_id), str(entry_id), data)


@router.post(
    "/{utility_id}/entries/{entry_id}/confirm", response_model=UtilityEntry,
    responses=ENTRY_ERRORS,
)
def confirm_payment(
    utility_id: UUID, entry_id: UUID, data: UtilityPaymentConfirmation,
    service: UtilityService = Depends(get_service),
) -> UtilityEntry:
    """An empty JSON object uses today's Lima date and the pending amount."""
    return service.confirm_payment(str(utility_id), str(entry_id), data)


@router.post(
    "/{utility_id}/entries/{entry_id}/undo", response_model=UtilityEntry,
    responses=ENTRY_ERRORS,
)
def undo_payment(
    utility_id: UUID, entry_id: UUID, service: UtilityService = Depends(get_service),
) -> UtilityEntry:
    """Clear the payment date, retaining the final amount and monthly period."""
    return service.undo_payment(str(utility_id), str(entry_id))

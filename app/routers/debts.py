"""Authenticated fixed monthly loan API."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.auth import get_current_user
from app.models.debt import (
    DebtCreate, DebtDetail, DebtInstallment, DebtMonthlySummary,
    DebtPaymentConfirmation, DebtPaymentCorrection, DebtUpdate,
)
from app.models.subscription import ErrorResponse
from app.services.debt_service import DebtService

router = APIRouter(
    prefix="/debts", tags=["debts"], dependencies=[Depends(get_current_user)],
    responses={500: {"model": ErrorResponse}},
)
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
}


def get_service(request: Request) -> DebtService:
    return request.app.state.debt_service


@router.post("", response_model=DebtDetail, status_code=status.HTTP_201_CREATED)
def create_debt(data: DebtCreate, service: DebtService = Depends(get_service)) -> DebtDetail:
    return service.create(data)


@router.get("", response_model=list[DebtDetail])
def list_debts(is_active: bool | None = None, service: DebtService = Depends(get_service)) -> list[DebtDetail]:
    return service.list_all(is_active)


@router.get("/summary", response_model=DebtMonthlySummary)
def monthly_summary(
    year: int = Query(ge=1900, le=9999), month: int = Query(ge=1, le=12),
    service: DebtService = Depends(get_service),
) -> DebtMonthlySummary:
    """Totals by due month, including archived loans; earlier arrears are separate."""
    return service.get_monthly_summary(year, month)


@router.get("/{debt_id}", response_model=DebtDetail, responses=ERRORS)
def get_debt(debt_id: UUID, service: DebtService = Depends(get_service)) -> DebtDetail:
    return service.get(str(debt_id))


@router.patch("/{debt_id}", response_model=DebtDetail, responses=ERRORS)
def update_debt(debt_id: UUID, data: DebtUpdate, service: DebtService = Depends(get_service)) -> DebtDetail:
    return service.update(str(debt_id), data)


@router.get("/{debt_id}/installments", response_model=list[DebtInstallment], responses=ERRORS)
def list_installments(debt_id: UUID, service: DebtService = Depends(get_service)) -> list[DebtInstallment]:
    return service.list_installments(str(debt_id))


@router.post("/{debt_id}/installments/{installment_id}/confirm", response_model=DebtInstallment, responses=ERRORS)
def confirm_payment(
    debt_id: UUID, installment_id: UUID, data: DebtPaymentConfirmation,
    service: DebtService = Depends(get_service),
) -> DebtInstallment:
    """Pay one full installment. Empty JSON defaults to today in Lima."""
    return service.confirm_payment(str(debt_id), str(installment_id), data)


@router.patch("/{debt_id}/installments/{installment_id}", response_model=DebtInstallment, responses=ERRORS)
def correct_payment(
    debt_id: UUID, installment_id: UUID, data: DebtPaymentCorrection,
    service: DebtService = Depends(get_service),
) -> DebtInstallment:
    return service.correct_payment(str(debt_id), str(installment_id), data)


@router.post("/{debt_id}/installments/{installment_id}/undo", response_model=DebtInstallment, responses=ERRORS)
def undo_payment(
    debt_id: UUID, installment_id: UUID, service: DebtService = Depends(get_service),
) -> DebtInstallment:
    return service.undo_payment(str(debt_id), str(installment_id))

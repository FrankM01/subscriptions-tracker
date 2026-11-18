"""Fixed-loan use cases with public API errors."""

from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.models.debt import (
    Debt, DebtCreate, DebtDetail, DebtInstallment, DebtMonthlySummary,
    DebtPaymentConfirmation, DebtPaymentCorrection, DebtUpdate,
)
from app.repositories.debt_repository import DebtConflictError, DebtNotFoundError, DebtRepository

T = TypeVar("T")


class DebtService:
    def __init__(self, repository: DebtRepository) -> None:
        self._repository = repository

    @staticmethod
    def _run(operation: Callable[[], T]) -> T:
        try:
            return operation()
        except DebtNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except DebtConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="Revisa las cuotas y el primer vencimiento del acuerdo.") from error
        except SQLAlchemyError as error:
            raise HTTPException(status_code=500, detail="No se pudo acceder a las deudas.") from error

    def create(self, data: DebtCreate) -> DebtDetail:
        return self._run(lambda: self._repository.add(Debt(debt_id=uuid4(), **data.model_dump())))

    def get(self, debt_id: str) -> DebtDetail:
        return self._run(lambda: self._repository.get(debt_id))

    def list_all(self, is_active: bool | None = None) -> list[DebtDetail]:
        return self._run(lambda: self._repository.list_all(is_active))

    def update(self, debt_id: str, data: DebtUpdate) -> DebtDetail:
        return self._run(lambda: self._repository.update(debt_id, data))

    def list_installments(self, debt_id: str) -> list[DebtInstallment]:
        return self.get(debt_id).installments

    def confirm_payment(self, debt_id: str, installment_id: str, data: DebtPaymentConfirmation) -> DebtInstallment:
        return self._run(lambda: self._repository.confirm_payment(debt_id, installment_id, data))

    def correct_payment(self, debt_id: str, installment_id: str, data: DebtPaymentCorrection) -> DebtInstallment:
        return self._run(lambda: self._repository.correct_payment(debt_id, installment_id, data))

    def undo_payment(self, debt_id: str, installment_id: str) -> DebtInstallment:
        return self._run(lambda: self._repository.undo_payment(debt_id, installment_id))

    def get_monthly_summary(self, year: int, month: int) -> DebtMonthlySummary:
        return self._run(lambda: self._repository.get_monthly_summary(year, month))

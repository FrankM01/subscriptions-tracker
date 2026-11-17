"""Utility catalog use cases and public errors."""

from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models.utility import (
    Utility, UtilityCreate, UtilityEntry, UtilityEntryCreate, UtilityEntryUpdate,
    UtilityMonthlySummary, UtilityPaymentConfirmation, UtilityUpdate,
)
from app.repositories.utility_repository import (
    UtilityRepository, UtilityNotFoundError, UtilityEntryConflictError,
)


T = TypeVar("T")


class UtilityService:
    def __init__(self, repository: UtilityRepository) -> None:
        self._repository = repository

    @staticmethod
    def _run(operation: Callable[[], T]) -> T:
        try:
            return operation()
        except UtilityNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UtilityEntryConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=500, detail="No se pudo acceder al catálogo de servicios."
            ) from error

    @staticmethod
    def _require(utility: Utility | None) -> Utility:
        if utility is None:
            raise HTTPException(status_code=404, detail="Servicio no encontrado.")
        return utility

    def create(self, data: UtilityCreate) -> Utility:
        utility = Utility(utility_id=uuid4(), **data.model_dump())
        return self._run(lambda: self._repository.add(utility))

    def get(self, utility_id: str) -> Utility:
        return self._require(self._run(lambda: self._repository.get(utility_id)))

    def list_all(self, is_active: bool | None = None) -> list[Utility]:
        return self._run(lambda: self._repository.list_all(is_active))

    def get_monthly_summary(self, year: int, month: int) -> UtilityMonthlySummary:
        return self._run(lambda: self._repository.get_monthly_summary(year, month))

    def update(self, utility_id: str, data: UtilityUpdate) -> Utility:
        return self._require(self._run(lambda: self._repository.update(utility_id, data)))

    def list_entries(self, utility_id: str) -> list[UtilityEntry]:
        self.get(utility_id)
        return self._run(lambda: self._repository.list_entries(utility_id))

    def create_entry(self, utility_id: str, data: UtilityEntryCreate) -> UtilityEntry:
        return self._run(lambda: self._repository.create_entry(utility_id, data))

    def update_entry(self, utility_id: str, entry_id: str, data: UtilityEntryUpdate) -> UtilityEntry:
        return self._run(lambda: self._repository.update_entry(utility_id, entry_id, data))

    def confirm_payment(
        self, utility_id: str, entry_id: str, data: UtilityPaymentConfirmation,
    ) -> UtilityEntry:
        return self._run(lambda: self._repository.confirm_payment(utility_id, entry_id, data))

    def undo_payment(self, utility_id: str, entry_id: str) -> UtilityEntry:
        return self._run(lambda: self._repository.undo_payment(utility_id, entry_id))

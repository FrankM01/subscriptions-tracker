"""Utility catalog use cases and public errors."""

from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models.utility import Utility, UtilityCreate, UtilityEntry, UtilityUpdate
from app.repositories.utility_repository import UtilityRepository


T = TypeVar("T")


class UtilityService:
    def __init__(self, repository: UtilityRepository) -> None:
        self._repository = repository

    @staticmethod
    def _run(operation: Callable[[], T]) -> T:
        try:
            return operation()
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

    def update(self, utility_id: str, data: UtilityUpdate) -> Utility:
        return self._require(self._run(lambda: self._repository.update(utility_id, data)))

    def list_entries(self, utility_id: str) -> list[UtilityEntry]:
        self.get(utility_id)
        return self._run(lambda: self._repository.list_entries(utility_id))

"""Daily-expense use cases with sanitized public errors."""
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.expense import (
    Expense, ExpenseCategory, ExpenseCategoryCreate, ExpenseCategoryDetail, ExpenseCategoryUpdate,
    ExpenseCreate, ExpenseFilters, ExpenseMonthlySummary, ExpensePage, ExpenseSubcategory, ExpenseUpdate,
)
from app.repositories.expense_repository import (
    ExpenseClassificationError, ExpenseConflictError, ExpenseNotFoundError, ExpenseRepository,
)

T = TypeVar("T")


class ExpenseService:
    def __init__(self, repository: ExpenseRepository) -> None:
        self._repository = repository

    @staticmethod
    def _run(operation: Callable[[], T], *, catalog: bool = False) -> T:
        try:
            return operation()
        except ExpenseNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExpenseConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ExpenseClassificationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="Revisa los datos del gasto.") from error
        except IntegrityError as error:
            if catalog:
                raise HTTPException(status_code=409, detail="Ya existe ese nombre en el mismo nivel. Revisa también las categorías archivadas.") from error
            raise HTTPException(status_code=500, detail="No se pudo acceder a los gastos diarios.") from error
        except SQLAlchemyError as error:
            raise HTTPException(status_code=500, detail="No se pudo acceder a los gastos diarios.") from error

    def list_categories(self) -> list[ExpenseCategoryDetail]:
        return self._run(self._repository.list_categories)

    def create_category(self, data: ExpenseCategoryCreate) -> ExpenseCategory:
        return self._run(lambda: self._repository.create_category(data), catalog=True)

    def update_category(self, category_id: str, data: ExpenseCategoryUpdate) -> ExpenseCategory:
        return self._run(lambda: self._repository.update_category(category_id, data), catalog=True)

    def create_subcategory(self, category_id: str, data: ExpenseCategoryCreate) -> ExpenseSubcategory:
        return self._run(lambda: self._repository.create_subcategory(category_id, data), catalog=True)

    def update_subcategory(self, category_id: str, subcategory_id: str, data: ExpenseCategoryUpdate) -> ExpenseSubcategory:
        return self._run(lambda: self._repository.update_subcategory(category_id, subcategory_id, data), catalog=True)

    def create(self, data: ExpenseCreate) -> Expense:
        return self._run(lambda: self._repository.create(data))

    def get(self, expense_id: str) -> Expense:
        return self._run(lambda: self._repository.get(expense_id))

    def update(self, expense_id: str, data: ExpenseUpdate) -> Expense:
        return self._run(lambda: self._repository.update(expense_id, data))

    def void(self, expense_id: str) -> Expense:
        return self._run(lambda: self._repository.set_voided(expense_id, True))

    def restore(self, expense_id: str) -> Expense:
        return self._run(lambda: self._repository.set_voided(expense_id, False))

    def list_all(self, filters: ExpenseFilters, state: str, limit: int, offset: int) -> ExpensePage:
        return self._run(lambda: self._repository.list_all(filters, state, limit, offset))

    def get_summary(self, filters: ExpenseFilters) -> ExpenseMonthlySummary:
        return self._run(lambda: self._repository.get_summary(filters))

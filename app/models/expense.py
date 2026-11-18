"""Daily expenses use a total amount, independent from their quantity."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.dates import today_in_lima

ExpenseAmount = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=9)]
ExpenseQuantity = Annotated[Decimal, Field(gt=0, decimal_places=3, max_digits=9)]


class ExpenseCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("El nombre de la categoría no puede estar vacío.")
        return value


class ExpenseCategory(ExpenseCategoryCreate):
    category_id: UUID
    is_active: bool = True


class ExpenseSubcategoryCreate(ExpenseCategoryCreate):
    category_id: UUID


class ExpenseSubcategory(ExpenseSubcategoryCreate):
    subcategory_id: UUID
    is_active: bool = True


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(max_length=200)
    quantity: ExpenseQuantity = Decimal("1")
    total_amount: ExpenseAmount
    expense_date: date = Field(default_factory=today_in_lima)
    category_id: UUID
    subcategory_id: UUID | None = None
    notes: str | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Escribe el producto o la descripción del gasto.")
        return value

    @field_validator("expense_date")
    @classmethod
    def validate_date(cls, value: date) -> date:
        if value < date(1900, 1, 1) or value > today_in_lima():
            raise ValueError("La fecha debe ser entre 1900 y hoy en Lima.")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class Expense(ExpenseCreate):
    expense_id: UUID
    is_voided: bool = False

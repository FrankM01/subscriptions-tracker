"""Daily expenses use a total amount, independent from their quantity."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class ExpenseCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = Field(default=None, strict=True)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return ExpenseCategoryCreate.normalize_name(value) if value is not None else None

    @model_validator(mode="after")
    def validate_update(self) -> "ExpenseCategoryUpdate":
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Incluye al menos un campo válido; nombre y estado no admiten null.")
        return self


class ExpenseCategoryDetail(ExpenseCategory):
    subcategories: list[ExpenseSubcategory]


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=200)
    quantity: ExpenseQuantity | None = None
    total_amount: ExpenseAmount | None = None
    expense_date: date | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    notes: str | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return ExpenseCreate.normalize_description(value) if value is not None else None

    @field_validator("expense_date")
    @classmethod
    def validate_date(cls, value: date | None) -> date | None:
        return ExpenseCreate.validate_date(value) if value is not None else None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return ExpenseCreate.normalize_notes(value)

    @model_validator(mode="after")
    def validate_update(self) -> "ExpenseUpdate":
        if not self.model_fields_set:
            raise ValueError("Incluye al menos un campo para actualizar.")
        for key in self.model_fields_set - {"notes", "subcategory_id"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} no puede ser null.")
        return self


class ExpenseFilters(BaseModel):
    year: int = Field(ge=1900, le=9999)
    month: int = Field(ge=1, le=12)
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    search: str = Field(default="", max_length=200)


class ExpensePage(BaseModel):
    items: list[Expense]
    total_count: int
    limit: int
    offset: int


class ExpenseGroupTotal(BaseModel):
    category_id: UUID
    category_name: str
    subcategory_id: UUID | None = None
    subcategory_name: str | None = None
    count: int
    total_amount: Decimal


class ExpenseDayTotal(BaseModel):
    expense_date: date
    count: int
    total_amount: Decimal
    cumulative_amount: Decimal


class ExpenseMonthlySummary(BaseModel):
    year: int
    month: int
    count: int
    total_amount: Decimal
    categories: list[ExpenseGroupTotal]
    subcategories: list[ExpenseGroupTotal]
    days: list[ExpenseDayTotal]

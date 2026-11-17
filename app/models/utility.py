"""Initial contracts for personal utility contributions (all amounts in PEN)."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.utils.dates import today_in_lima


PersonalAmount = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=9)]


class UtilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre del servicio no puede estar vacío.")
        return value

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class Utility(UtilityCreate):
    utility_id: UUID
    is_active: bool = True


class UtilityEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1900, le=9999)
    month: int = Field(ge=1, le=12)
    amount: PersonalAmount
    due_date: date | None = None
    paid_date: date | None = None
    notes: str | None = None

    @field_validator("paid_date")
    @classmethod
    def payment_must_not_be_future(cls, value: date | None) -> date | None:
        if value is not None and value > today_in_lima():
            raise ValueError("La fecha de pago no puede estar en el futuro.")
        return value


class UtilityEntry(UtilityEntryCreate):
    entry_id: UUID
    utility_id: UUID

    @computed_field
    @property
    def status(self) -> str:
        return "paid" if self.paid_date is not None else "pending"

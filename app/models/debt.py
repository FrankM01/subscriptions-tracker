"""Contracts for fixed monthly loans; previous payments are declared progress."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.utils.dates import today_in_lima


DebtAmount = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=9)]


class DebtCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    creditor: str
    installment_amount: DebtAmount
    total_installments: int = Field(gt=0, strict=True)
    previously_paid_installments: int = Field(default=0, ge=0, strict=True)
    first_due_date: date | None = None
    notes: str | None = None

    @field_validator("name", "creditor")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre y el acreedor no pueden estar vacíos.")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def validate_schedule(self) -> "DebtCreate":
        if self.previously_paid_installments > self.total_installments:
            raise ValueError("Las cuotas pagadas no pueden superar el total.")
        remaining = self.total_installments - self.previously_paid_installments
        if remaining:
            if self.first_due_date is None:
                raise ValueError("Indica el primer vencimiento pendiente.")
            last_month = (
                (self.first_due_date.year - 1) * 12
                + self.first_due_date.month - 1 + remaining - 1
            )
            if last_month >= 9999 * 12:
                raise ValueError("El calendario supera el año 9999.")
        elif self.first_due_date is not None:
            raise ValueError("Una deuda liquidada no tiene primer vencimiento pendiente.")
        return self


class Debt(DebtCreate):
    debt_id: UUID
    is_active: bool = True


class DebtInstallment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installment_id: UUID
    debt_id: UUID
    number: int = Field(gt=0, strict=True)
    amount: DebtAmount
    due_date: date
    paid_date: date | None = None

    @computed_field
    @property
    def status(self) -> str:
        return "paid" if self.paid_date else "pending"


class DebtPaymentConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_date: date | None = None

    @field_validator("paid_date")
    @classmethod
    def payment_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > today_in_lima():
            raise ValueError("La fecha de pago no puede estar en el futuro.")
        return value


class DebtPaymentCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_date: date

    @field_validator("paid_date")
    @classmethod
    def payment_not_in_future(cls, value: date) -> date:
        DebtPaymentConfirmation.payment_not_in_future(value)
        return value


class DebtUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    creditor: str | None = None
    notes: str | None = None
    is_active: bool | None = Field(default=None, strict=True)
    installment_amount: DebtAmount | None = None
    total_installments: int | None = Field(default=None, gt=0, strict=True)
    previously_paid_installments: int | None = Field(default=None, ge=0, strict=True)
    first_due_date: date | None = None

    @field_validator("name", "creditor")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        return DebtCreate.nonblank(value) if value is not None else None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return DebtCreate.normalize_notes(value)

    @model_validator(mode="after")
    def validate_update(self) -> "DebtUpdate":
        if not self.model_fields_set:
            raise ValueError("Incluye al menos un campo para actualizar.")
        for name in self.model_fields_set - {"notes", "first_due_date"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} no puede ser null.")
        return self


class DebtDetail(Debt):
    paid_installments: int
    pending_installments: int
    remaining_balance: Decimal
    next_due_date: date | None
    overdue_installments: int
    status: str
    schedule_editable: bool
    installments: list[DebtInstallment]


class DebtMonthlySummary(BaseModel):
    year: int
    month: int
    pending_count: int
    paid_count: int
    total_pending: Decimal
    total_paid: Decimal
    overdue_before_month_count: int
    total_overdue_before_month: Decimal

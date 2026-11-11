from enum import Enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.dates import today_in_lima


class BillingCycle(str, Enum):
    monthly = "monthly"
    yearly = "yearly"


class Subscription(BaseModel):
    subscription_id: UUID
    name: str
    cost: Decimal
    billing_cycle: BillingCycle
    renewal_date: date
    is_active: bool = True


class SubscriptionCreate(BaseModel):
    name: str
    cost: Decimal = Field(..., gt=0, decimal_places=2)
    billing_cycle: BillingCycle
    renewal_date: date
    is_active: bool = True

    @field_validator("renewal_date")
    @classmethod
    def renewal_date_must_be_future(cls, v: date) -> date:
        if v <= today_in_lima():
            raise ValueError("renewal_date must be a future date")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    cost: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    billing_cycle: BillingCycle | None = None
    renewal_date: date | None = None
    is_active: bool | None = None

    @field_validator("renewal_date")
    @classmethod
    def renewal_date_must_be_future(cls, v: date | None) -> date | None:
        if v is not None and v <= today_in_lima():
            raise ValueError("renewal_date must be a future date")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def must_include_a_non_null_update(self) -> "SubscriptionUpdate":
        values = self.model_dump(exclude_unset=True)
        if not values or all(value is None for value in values.values()):
            raise ValueError("At least one non-null field must be provided for update")
        return self


class RenewalConfirmation(BaseModel):
    """Command to confirm the specific currently pending billing period."""

    scheduled_date: date = Field(
        description="Expected pending renewal date; prevents confirming a stale period."
    )
    paid_date: date | None = Field(
        default=None,
        description="Actual payment date. Defaults to today in America/Lima.",
    )
    paid_amount: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
        description=(
            "Amount paid in PEN as a decimal string. Defaults to the current subscription cost."
        ),
    )

    @field_validator("paid_date")
    @classmethod
    def paid_date_must_not_be_future(cls, value: date | None) -> date | None:
        if value is not None and value > today_in_lima():
            raise ValueError("paid_date cannot be in the future")
        return value


class RenewalEntry(BaseModel):
    renewal_id: int = Field(description="Database identifier for this payment record.")
    subscription_id: UUID = Field(description="Subscription associated with this payment.")
    scheduled_date: date = Field(description="Renewal date that this payment confirms.")
    paid_date: date = Field(description="Calendar date on which the payment was made.")
    paid_amount: Decimal = Field(
        description="Amount paid in PEN, serialized as a decimal string."
    )


class SummaryResponse(BaseModel):
    total_monthly_cost: Decimal


class RenewalAlert(BaseModel):
    subscription_id: UUID
    name: str
    renewal_date: date
    billing_cycle: BillingCycle
    days_until_renewal: int = Field(
        description="Days until renewal; negative values identify overdue pending renewals."
    )


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable API error message.")

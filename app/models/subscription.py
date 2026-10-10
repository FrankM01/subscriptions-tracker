from enum import Enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    cost: Decimal = Field(..., gt=0)
    billing_cycle: BillingCycle
    renewal_date: date
    is_active: bool = True

    @field_validator("renewal_date")
    @classmethod
    def renewal_date_must_be_future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("renewal_date must be a future date")
        return v


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    cost: Decimal | None = Field(default=None, gt=0)
    billing_cycle: BillingCycle | None = None
    renewal_date: date | None = None
    is_active: bool | None = None

    @field_validator("renewal_date")
    @classmethod
    def renewal_date_must_be_future(cls, v: date | None) -> date | None:
        if v is not None and v <= date.today():
            raise ValueError("renewal_date must be a future date")
        return v


class SummaryResponse(BaseModel):
    total_monthly_cost: Decimal


class RenewalAlert(BaseModel):
    subscription_id: UUID
    name: str
    renewal_date: date
    billing_cycle: BillingCycle
    days_until_renewal: int


class ErrorResponse(BaseModel):
    detail: str

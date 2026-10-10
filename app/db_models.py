"""SQLAlchemy persistence models for subscriptions and renewal history."""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubscriptionRecord(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_subscriptions_name_nonempty"),
        CheckConstraint("cost_cents > 0", name="ck_subscriptions_cost_positive"),
        CheckConstraint(
            "billing_cycle IN ('monthly', 'yearly')",
            name="ck_subscriptions_billing_cycle",
        ),
        CheckConstraint("anchor_day BETWEEN 1 AND 31", name="ck_subscriptions_anchor_day"),
    )

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    renewal_date: Mapped["date"] = mapped_column(Date, nullable=False)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )

    renewals: Mapped[list["RenewalRecord"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", passive_deletes=True
    )


class RenewalRecord(Base):
    __tablename__ = "renewals"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "scheduled_date", name="uq_renewals_subscription_scheduled"
        ),
        CheckConstraint("paid_amount_cents > 0", name="ck_renewals_paid_amount_positive"),
        CheckConstraint(
            "resulting_billing_cycle IN ('monthly', 'yearly')",
            name="ck_renewals_resulting_billing_cycle",
        ),
        CheckConstraint(
            "resulting_anchor_day BETWEEN 1 AND 31",
            name="ck_renewals_resulting_anchor_day",
        ),
    )

    renewal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_date: Mapped["date"] = mapped_column(Date, nullable=False)
    paid_date: Mapped["date"] = mapped_column(Date, nullable=False)
    paid_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_renewal_date: Mapped["date"] = mapped_column(Date, nullable=False)
    resulting_billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    resulting_anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)

    subscription: Mapped[SubscriptionRecord] = relationship(back_populates="renewals")

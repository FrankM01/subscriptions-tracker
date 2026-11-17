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
    true,
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
        Boolean, nullable=False, default=True, server_default=true()
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


class UtilityRecord(Base):
    """Personal utility catalog; archive rather than delete its history."""

    __tablename__ = "utilities"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_utilities_name_nonempty"),
    )

    utility_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    entries: Mapped[list["UtilityEntryRecord"]] = relationship(
        back_populates="utility", passive_deletes="all"
    )


class UtilityEntryRecord(Base):
    """One personal contribution per service/month; paid_date implies payment."""

    __tablename__ = "utility_entries"
    __table_args__ = (
        UniqueConstraint("utility_id", "year", "month", name="uq_utility_entries_period"),
        CheckConstraint("year BETWEEN 1900 AND 9999", name="ck_utility_entries_year"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_utility_entries_month"),
        CheckConstraint("amount_cents > 0", name="ck_utility_entries_amount_positive"),
    )

    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    utility_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("utilities.utility_id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    paid_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    utility: Mapped[UtilityRecord] = relationship(back_populates="entries")

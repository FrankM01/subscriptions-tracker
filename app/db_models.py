"""SQLAlchemy persistence models for subscriptions and renewal history."""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    true,
    false,
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


class DebtRecord(Base):
    """Fixed agreement; declared previous payments have no invented history."""

    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_debts_name_nonempty"),
        CheckConstraint("length(trim(creditor)) > 0", name="ck_debts_creditor_nonempty"),
        CheckConstraint("installment_amount_cents > 0", name="ck_debts_amount_positive"),
        CheckConstraint("total_installments > 0", name="ck_debts_total_positive"),
        CheckConstraint(
            "previously_paid_installments BETWEEN 0 AND total_installments",
            name="ck_debts_previous_range",
        ),
        CheckConstraint(
            "(previously_paid_installments < total_installments AND first_due_date IS NOT NULL) "
            "OR (previously_paid_installments = total_installments AND first_due_date IS NULL)",
            name="ck_debts_first_due_date",
        ),
    )

    debt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    creditor: Mapped[str] = mapped_column(Text, nullable=False)
    installment_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    previously_paid_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    first_due_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true(),
    )
    installments: Mapped[list["DebtInstallmentRecord"]] = relationship(
        back_populates="debt", passive_deletes="all",
    )


class DebtInstallmentRecord(Base):
    __tablename__ = "debt_installments"
    __table_args__ = (
        UniqueConstraint("debt_id", "number", name="uq_debt_installments_number"),
        CheckConstraint("number > 0", name="ck_debt_installments_number_positive"),
        CheckConstraint("amount_cents > 0", name="ck_debt_installments_amount_positive"),
    )

    installment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    debt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("debts.debt_id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[date | None] = mapped_column(Date)
    debt: Mapped[DebtRecord] = relationship(back_populates="installments")


class ExpenseCategoryRecord(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_expense_categories_name"),
        CheckConstraint("length(trim(name_key)) > 0", name="ck_expense_categories_key"),
        UniqueConstraint("name_key", name="uq_expense_categories_key"),
    )

    category_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())


class ExpenseSubcategoryRecord(Base):
    __tablename__ = "expense_subcategories"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_expense_subcategories_name"),
        CheckConstraint("length(trim(name_key)) > 0", name="ck_expense_subcategories_key"),
        UniqueConstraint("category_id", "name_key", name="uq_expense_subcategories_key"),
        UniqueConstraint("category_id", "subcategory_id", name="uq_expense_subcategories_parent"),
    )

    subcategory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("expense_categories.category_id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())


class ExpenseRecord(Base):
    """Quantity is measured in thousandths; total is never multiplied by it."""

    __tablename__ = "expenses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "subcategory_id"],
            ["expense_subcategories.category_id", "expense_subcategories.subcategory_id"],
            ondelete="RESTRICT", name="fk_expenses_subcategory_parent",
        ),
        CheckConstraint("length(trim(description)) > 0", name="ck_expenses_description"),
        CheckConstraint("quantity_millis BETWEEN 1 AND 999999999", name="ck_expenses_quantity"),
        CheckConstraint("total_amount_cents BETWEEN 1 AND 999999999", name="ck_expenses_total"),
    )

    expense_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_millis: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("expense_categories.category_id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    subcategory_id: Mapped[str | None] = mapped_column(String(36))
    notes: Mapped[str | None] = mapped_column(Text)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

"""Atomic fixed-loan operations for SQLite and PostgreSQL."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload

from app.db_models import DebtInstallmentRecord, DebtRecord
from app.models.debt import (
    Debt, DebtDetail, DebtInstallment, DebtMonthlySummary, DebtPaymentConfirmation,
    DebtPaymentCorrection, DebtUpdate,
)
from app.services.debt_schedule import build_installments
from app.utils.dates import today_in_lima


class DebtNotFoundError(LookupError):
    pass


class DebtConflictError(RuntimeError):
    pass


SCHEDULE_FIELDS = {
    "installment_amount", "total_installments", "previously_paid_installments", "first_due_date",
}


def money(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


class DebtRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _agreement(record: DebtRecord) -> Debt:
        return Debt(
            debt_id=UUID(record.debt_id), name=record.name, creditor=record.creditor,
            installment_amount=money(record.installment_amount_cents),
            total_installments=record.total_installments,
            previously_paid_installments=record.previously_paid_installments,
            first_due_date=record.first_due_date, notes=record.notes, is_active=record.is_active,
        )

    @staticmethod
    def _installment(record: DebtInstallmentRecord) -> DebtInstallment:
        return DebtInstallment(
            installment_id=UUID(record.installment_id), debt_id=UUID(record.debt_id),
            number=record.number, amount=money(record.amount_cents),
            due_date=record.due_date, paid_date=record.paid_date,
        )

    def _detail(self, record: DebtRecord) -> DebtDetail:
        installments = [self._installment(row) for row in sorted(record.installments, key=lambda r: r.number)]
        pending = [row for row in installments if row.paid_date is None]
        confirmed = len(installments) - len(pending)
        return DebtDetail(
            **self._agreement(record).model_dump(), installments=installments,
            paid_installments=record.previously_paid_installments + confirmed,
            pending_installments=len(pending),
            remaining_balance=sum((row.amount for row in pending), Decimal("0.00")),
            next_due_date=min((row.due_date for row in pending), default=None),
            overdue_installments=sum(row.due_date < today_in_lima() for row in pending),
            status="settled" if not pending else "pending", schedule_editable=not confirmed,
        )

    @contextmanager
    def _transaction(self, debt_id: str) -> Iterator[tuple[Session, DebtRecord]]:
        # Every edit/payment locks the same parent, including schedule replacement.
        with Session(self._engine) as session:
            try:
                if self._engine.dialect.name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                record = session.scalar(select(DebtRecord).where(
                    DebtRecord.debt_id == debt_id,
                ).with_for_update())
                if record is None:
                    raise DebtNotFoundError("Deuda no encontrada.")
                yield session, record
                session.commit()
            except Exception:
                session.rollback()
                raise

    @staticmethod
    def _rows(debt: Debt) -> list[DebtInstallmentRecord]:
        return [DebtInstallmentRecord(
            installment_id=str(row.installment_id), debt_id=str(row.debt_id), number=row.number,
            amount_cents=int(row.amount * 100), due_date=row.due_date,
        ) for row in build_installments(debt)]

    def add(self, debt: Debt) -> DebtDetail:
        values = debt.model_dump(exclude={"installment_amount", "debt_id"})
        record = DebtRecord(
            **values, debt_id=str(debt.debt_id),
            installment_amount_cents=int(debt.installment_amount * 100),
        )
        record.installments = self._rows(debt)
        with Session(self._engine) as session, session.begin():
            session.add(record)
            session.flush()
            result = self._detail(record)
        return result

    def get(self, debt_id: str) -> DebtDetail:
        # Use the same transaction as writes so metadata and installments are consistent.
        with self._transaction(debt_id) as (_, record):
            return self._detail(record)

    def list_all(self, is_active: bool | None = None) -> list[DebtDetail]:
        # One statement reads agreements and installments from the same snapshot.
        statement = select(DebtRecord).options(joinedload(DebtRecord.installments)).order_by(
            DebtRecord.name, DebtRecord.debt_id,
        )
        if is_active is not None:
            statement = statement.where(DebtRecord.is_active == is_active)
        with Session(self._engine) as session:
            return [self._detail(row) for row in session.scalars(statement).unique()]

    def update(self, debt_id: str, data: DebtUpdate) -> DebtDetail:
        with self._transaction(debt_id) as (session, record):
            current = self._agreement(record)
            fields = data.model_dump(exclude_unset=True)
            changed = {key for key in fields if fields[key] != getattr(current, key)}
            schedule_changed = bool(changed & SCHEDULE_FIELDS)
            if schedule_changed and any(row.paid_date is not None for row in record.installments):
                raise DebtConflictError("No se puede cambiar el acuerdo con pagos confirmados.")
            # Validate the merged agreement before touching any rows, including null/date rules.
            agreement = Debt.model_validate({**current.model_dump(), **fields})
            if schedule_changed:
                session.execute(delete(DebtInstallmentRecord).where(
                    DebtInstallmentRecord.debt_id == debt_id,
                ))
                session.expire(record, ["installments"])
                record.installments = self._rows(agreement)
            for key, value in fields.items():
                if key == "installment_amount":
                    record.installment_amount_cents = int(value * 100)
                else:
                    setattr(record, key, value)
            session.flush()
            result = self._detail(record)
        return result

    @staticmethod
    def _require_installment(session: Session, debt_id: str, installment_id: str) -> DebtInstallmentRecord:
        row = session.scalar(select(DebtInstallmentRecord).where(
            DebtInstallmentRecord.debt_id == debt_id,
            DebtInstallmentRecord.installment_id == installment_id,
        ))
        if row is None:
            raise DebtNotFoundError("Cuota no encontrada.")
        return row

    def confirm_payment(
        self, debt_id: str, installment_id: str, data: DebtPaymentConfirmation,
    ) -> DebtInstallment:
        with self._transaction(debt_id) as (session, _):
            row = self._require_installment(session, debt_id, installment_id)
            if row.paid_date is not None:
                raise DebtConflictError("El pago ya está confirmado.")
            row.paid_date = data.paid_date or today_in_lima()
            session.flush()
            result = self._installment(row)
        return result

    def correct_payment(
        self, debt_id: str, installment_id: str, data: DebtPaymentCorrection,
    ) -> DebtInstallment:
        with self._transaction(debt_id) as (session, _):
            row = self._require_installment(session, debt_id, installment_id)
            if row.paid_date is None:
                raise DebtConflictError("Primero confirma el pago de la cuota.")
            row.paid_date = data.paid_date
            session.flush()
            result = self._installment(row)
        return result

    def undo_payment(self, debt_id: str, installment_id: str) -> DebtInstallment:
        with self._transaction(debt_id) as (session, _):
            row = self._require_installment(session, debt_id, installment_id)
            if row.paid_date is None:
                raise DebtConflictError("No hay un pago confirmado para revertir.")
            row.paid_date = None
            session.flush()
            result = self._installment(row)
        return result

    def get_monthly_summary(self, year: int, month: int) -> DebtMonthlySummary:
        first = date(year, month, 1)
        pending = DebtInstallmentRecord.paid_date.is_(None)
        in_month = (func.extract("year", DebtInstallmentRecord.due_date) == year) & (
            func.extract("month", DebtInstallmentRecord.due_date) == month
        )
        conditions = {
            "pending": in_month & pending,
            "paid": in_month & DebtInstallmentRecord.paid_date.is_not(None),
            "overdue": (DebtInstallmentRecord.due_date < first) & pending
                & (DebtInstallmentRecord.due_date < today_in_lima()),
        }
        columns = []
        for name, condition in conditions.items():
            columns.extend([
                func.coalesce(func.sum(case((condition, 1), else_=0)), 0).label(name + "_count"),
                func.coalesce(func.sum(case((condition, DebtInstallmentRecord.amount_cents), else_=0)), 0).label(name + "_cents"),
            ])
        with Session(self._engine) as session:
            totals = session.execute(select(*columns)).one()
            return DebtMonthlySummary(
                year=year, month=month, pending_count=totals.pending_count, paid_count=totals.paid_count,
                total_pending=money(totals.pending_cents), total_paid=money(totals.paid_cents),
                overdue_before_month_count=totals.overdue_count,
                total_overdue_before_month=money(totals.overdue_cents),
            )

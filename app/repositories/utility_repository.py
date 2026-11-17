"""Persistent utility catalog, shared by PostgreSQL and SQLite."""

from decimal import Decimal
from contextlib import contextmanager
from collections.abc import Iterator
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db_models import UtilityEntryRecord, UtilityRecord
from app.models.utility import (
    Utility, UtilityEntry, UtilityEntryCreate, UtilityEntryUpdate,
    UtilityPaymentConfirmation, UtilityUpdate,
)
from app.utils.dates import today_in_lima


class UtilityNotFoundError(LookupError):
    pass


class UtilityEntryConflictError(RuntimeError):
    pass


class UtilityRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _to_model(record: UtilityRecord) -> Utility:
        return Utility(
            utility_id=record.utility_id,
            name=record.name,
            provider=record.provider,
            is_active=record.is_active,
        )

    def add(self, utility: Utility) -> Utility:
        with Session(self._engine) as session, session.begin():
            session.add(UtilityRecord(**utility.model_dump(mode="json")))
        return utility

    def get(self, utility_id: str) -> Utility | None:
        with Session(self._engine) as session:
            record = session.get(UtilityRecord, utility_id)
            return self._to_model(record) if record is not None else None

    def list_all(self, is_active: bool | None = None) -> list[Utility]:
        statement = select(UtilityRecord).order_by(UtilityRecord.name, UtilityRecord.utility_id)
        if is_active is not None:
            statement = statement.where(UtilityRecord.is_active == is_active)
        with Session(self._engine) as session:
            return [self._to_model(record) for record in session.scalars(statement)]

    def update(self, utility_id: str, data: UtilityUpdate) -> Utility | None:
        # Update only supplied fields in a single statement, avoiding overwriting
        # another operation's edits to unrelated fields (e.g. archive vs rename).
        statement = (
            update(UtilityRecord)
            .where(UtilityRecord.utility_id == utility_id)
            .values(**data.model_dump(exclude_unset=True))
            .returning(UtilityRecord)
        )
        with Session(self._engine) as session, session.begin():
            record = session.scalars(statement).one_or_none()
            result = self._to_model(record) if record is not None else None
        return result

    def list_entries(self, utility_id: str) -> list[UtilityEntry]:
        statement = (
            select(UtilityEntryRecord)
            .where(UtilityEntryRecord.utility_id == utility_id)
            .order_by(UtilityEntryRecord.year.desc(), UtilityEntryRecord.month.desc())
        )
        with Session(self._engine) as session:
            return [self._to_entry(record) for record in session.scalars(statement)]

    @staticmethod
    def _to_entry(record: UtilityEntryRecord) -> UtilityEntry:
        return UtilityEntry(
            entry_id=record.entry_id, utility_id=record.utility_id,
            year=record.year, month=record.month,
            amount=(Decimal(record.amount_cents) / 100).quantize(Decimal("0.01")),
            due_date=record.due_date, paid_date=record.paid_date, notes=record.notes,
        )

    @contextmanager
    def _entry_transaction(self, utility_id: str) -> Iterator[tuple[Session, UtilityRecord]]:
        """Serialize monthly writes per service (SQLite locks before reading)."""
        with Session(self._engine) as session:
            try:
                if self._engine.dialect.name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                utility = session.scalar(
                    select(UtilityRecord)
                    .where(UtilityRecord.utility_id == utility_id)
                    .with_for_update()
                )
                if utility is None:
                    raise UtilityNotFoundError("Servicio no encontrado.")
                yield session, utility
                session.commit()
            except Exception:
                session.rollback()
                raise

    @staticmethod
    def _require_entry(session: Session, utility_id: str, entry_id: str) -> UtilityEntryRecord:
        entry = session.scalar(select(UtilityEntryRecord).where(
            UtilityEntryRecord.entry_id == entry_id,
            UtilityEntryRecord.utility_id == utility_id,
        ))
        if entry is None:
            raise UtilityNotFoundError("Registro mensual no encontrado.")
        return entry

    @staticmethod
    def _check_period(
        session: Session, utility_id: str, year: int, month: int, entry_id: str | None = None,
    ) -> None:
        statement = select(UtilityEntryRecord.entry_id).where(
            UtilityEntryRecord.utility_id == utility_id,
            UtilityEntryRecord.year == year, UtilityEntryRecord.month == month,
        )
        if entry_id is not None:
            statement = statement.where(UtilityEntryRecord.entry_id != entry_id)
        if session.scalar(statement) is not None:
            raise UtilityEntryConflictError("Ya existe un registro para ese servicio y período.")

    def create_entry(self, utility_id: str, data: UtilityEntryCreate) -> UtilityEntry:
        with self._entry_transaction(utility_id) as (session, utility):
            if not utility.is_active:
                raise UtilityEntryConflictError("Reactiva el servicio antes de registrar otro período.")
            self._check_period(session, utility_id, data.year, data.month)
            record = UtilityEntryRecord(
                entry_id=str(uuid4()), utility_id=utility_id,
                **data.model_dump(exclude={"amount"}), amount_cents=int(data.amount * 100),
            )
            session.add(record)
            session.flush()
            result = self._to_entry(record)
        return result

    def update_entry(
        self, utility_id: str, entry_id: str, data: UtilityEntryUpdate,
    ) -> UtilityEntry:
        with self._entry_transaction(utility_id) as (session, _):
            record = self._require_entry(session, utility_id, entry_id)
            fields = data.model_dump(exclude_unset=True)
            if "paid_date" in fields and record.paid_date is None:
                raise UtilityEntryConflictError("Usa la confirmación para registrar el pago pendiente.")
            self._check_period(
                session, utility_id, fields.get("year", record.year),
                fields.get("month", record.month), entry_id,
            )
            for field, value in fields.items():
                if field == "amount":
                    record.amount_cents = int(value * 100)
                else:
                    setattr(record, field, value)
            session.flush()
            result = self._to_entry(record)
        return result

    def confirm_payment(
        self, utility_id: str, entry_id: str, data: UtilityPaymentConfirmation,
    ) -> UtilityEntry:
        with self._entry_transaction(utility_id) as (session, _):
            record = self._require_entry(session, utility_id, entry_id)
            if record.paid_date is not None:
                raise UtilityEntryConflictError("El pago ya está confirmado.")
            record.paid_date = data.paid_date or today_in_lima()
            if data.amount is not None:
                record.amount_cents = int(data.amount * 100)
            session.flush()
            result = self._to_entry(record)
        return result

    def undo_payment(self, utility_id: str, entry_id: str) -> UtilityEntry:
        with self._entry_transaction(utility_id) as (session, _):
            record = self._require_entry(session, utility_id, entry_id)
            if record.paid_date is None:
                raise UtilityEntryConflictError("No hay un pago confirmado para revertir.")
            record.paid_date = None
            session.flush()
            result = self._to_entry(record)
        return result

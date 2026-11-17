"""Persistent utility catalog, shared by PostgreSQL and SQLite."""

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db_models import UtilityEntryRecord, UtilityRecord
from app.models.utility import Utility, UtilityEntry, UtilityUpdate


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
            return [
                UtilityEntry(
                    entry_id=record.entry_id, utility_id=record.utility_id,
                    year=record.year, month=record.month,
                    amount=(Decimal(record.amount_cents) / 100).quantize(Decimal("0.01")),
                    due_date=record.due_date, paid_date=record.paid_date, notes=record.notes,
                )
                for record in session.scalars(statement)
            ]

"""Exercise the new domain and migration without touching the local database."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, DEFAULT_DATABASE_PATH, make_engine
from app.db_models import UtilityEntryRecord, UtilityRecord
from app.models.utility import UtilityCreate, UtilityEntry, UtilityEntryCreate
from app.utils.dates import today_in_lima


def test_personal_amount_and_payment_status_keep_period_separate():
    entry = UtilityEntry(
        entry_id=uuid4(), utility_id=uuid4(), year=2025, month=11,
        amount="45.10", paid_date=date(2025, 12, 2),
    )
    assert entry.amount == Decimal("45.10")
    assert entry.model_dump(mode="json")["amount"] == "45.10"
    assert entry.status == "paid"
    assert entry.month == 11
    assert entry.model_copy(update={"paid_date": None}).status == "pending"
    assert UtilityCreate(name="  Luz  ", provider=" ").model_dump() == {
        "name": "Luz", "provider": None,
    }


@pytest.mark.parametrize("changes", [
    {"amount": "0"}, {"amount": "-1"}, {"amount": "1.001"},
    {"amount": "10000000"}, {"amount": "NaN"},
    {"month": 0}, {"month": 13}, {"year": 1899}, {"year": 10000},
    {"paid_date": today_in_lima() + timedelta(days=1)},
    {"total_household_amount": "200.00"},
])
def test_invalid_monthly_contributions_are_rejected(changes):
    payload = {"year": 2026, "month": 11, "amount": "45.00", **changes}
    with pytest.raises(ValidationError):
        UtilityEntryCreate(**payload)


def test_blank_service_is_rejected():
    with pytest.raises(ValidationError):
        UtilityCreate(name="  ")


def test_upgrade_preserves_existing_data_and_downgrade_removes_only_new_tables(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", database_url)
    config = Config(str(DEFAULT_DATABASE_PATH.parent.parent / "alembic.ini"))
    command.upgrade(config, "406d989e7e68")
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO subscriptions (subscription_id, name, cost_cents, "
                "billing_cycle, renewal_date, anchor_day, is_active) VALUES "
                "('existing', 'Internet', 1000, 'monthly', '2026-12-01', 1, 1)"
            ))
            connection.execute(text(
                "INSERT INTO renewals (subscription_id, scheduled_date, paid_date, "
                "paid_amount_cents, resulting_renewal_date, resulting_billing_cycle, "
                "resulting_anchor_day) VALUES ('existing', '2026-11-01', '2026-11-01', "
                "1000, '2026-12-01', 'monthly', 1)"
            ))
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT name FROM subscriptions")) == "Internet"
            assert connection.scalar(text("SELECT count(*) FROM renewals")) == 1
        command.downgrade(config, "406d989e7e68")
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version", "subscriptions", "renewals",
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM subscriptions")) == 1
            assert connection.scalar(text("SELECT count(*) FROM renewals")) == 1
    finally:
        engine.dispose()


def test_archiving_and_reopening_database_preserve_history(tmp_path):
    url = f"sqlite:///{tmp_path / 'history.db'}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.add(UtilityRecord(utility_id="utility", name="Luz"))
        session.flush()
        session.add(UtilityEntryRecord(
            entry_id="nov", utility_id="utility", year=2026, month=11,
            amount_cents=4510, paid_date=date(2026, 11, 1),
        ))
    with Session(engine) as session, session.begin():
        session.get(UtilityRecord, "utility").is_active = False
    engine.dispose()
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            utility = session.get(UtilityRecord, "utility")
            assert utility.is_active is False
            assert utility.entries[0].amount_cents == 4510
            assert utility.entries[0].paid_date == date(2026, 11, 1)
    finally:
        engine.dispose()


@pytest.mark.parametrize("changes", [
    {"entry_id": "duplicate"},
    {"entry_id": "bad-amount", "month": 10, "amount_cents": 0},
    {"entry_id": "bad-month", "month": 13},
    {"entry_id": "bad-year", "year": 1899},
    {"entry_id": "orphan", "utility_id": "missing"},
])
def test_database_enforces_period_amount_and_parent_constraints(changes):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    payload = dict(entry_id="first", utility_id="utility", year=2026, month=11, amount_cents=4500)
    try:
        with Session(engine) as session, session.begin():
            session.add(UtilityRecord(utility_id="utility", name="Luz"))
            session.flush()
            session.add(UtilityEntryRecord(**payload))
        with Session(engine) as session, pytest.raises(IntegrityError):
            with session.begin():
                session.add(UtilityEntryRecord(**{**payload, **changes}))
        with Session(engine) as session, pytest.raises(IntegrityError):
            with session.begin():
                session.delete(session.get(UtilityRecord, "utility"))
        with Session(engine) as session:
            assert len(session.scalars(select(UtilityEntryRecord)).all()) == 1
    finally:
        engine.dispose()

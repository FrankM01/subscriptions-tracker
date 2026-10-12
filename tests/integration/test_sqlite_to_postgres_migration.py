"""Opt-in tests for the SQLite-to-PostgreSQL data migration."""

from contextlib import closing
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import db_models  # noqa: F401 - register ORM metadata
from app.database import Base, DEFAULT_DATABASE_PATH, make_engine
from app.db_models import RenewalRecord, SubscriptionRecord
from app.repositories.subscription_repository import SubscriptionRepository
from app.sqlite_to_postgres import MigrationError, migrate_sqlite_to_postgres


PROJECT_ROOT = DEFAULT_DATABASE_PATH.parent.parent
POSTGRES_TEST_URL = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")


def _create_valid_source(path: Path) -> str:
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    subscription_id = str(uuid4())
    try:
        with Session(engine) as session:
            subscription = SubscriptionRecord(
                subscription_id=subscription_id,
                name="Migrated subscription",
                cost_cents=1799,
                billing_cycle="monthly",
                renewal_date=date(2026, 4, 30),
                anchor_day=31,
                is_active=False,
            )
            subscription.renewals.append(
                RenewalRecord(
                    renewal_id=93,
                    scheduled_date=date(2026, 3, 31),
                    paid_date=date(2026, 4, 1),
                    paid_amount_cents=1899,
                    resulting_renewal_date=date(2026, 4, 30),
                    resulting_billing_cycle="monthly",
                    resulting_anchor_day=31,
                )
            )
            session.add(subscription)
            session.commit()
    finally:
        engine.dispose()
    return subscription_id


def _create_invalid_source(path: Path) -> None:
    """Build a structurally readable SQLite file with a row rejected by PG."""
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE subscriptions (
                subscription_id TEXT, name TEXT, cost_cents INTEGER,
                billing_cycle TEXT, renewal_date TEXT, anchor_day INTEGER,
                is_active INTEGER
            );
            CREATE TABLE renewals (
                renewal_id INTEGER, subscription_id TEXT, scheduled_date TEXT,
                paid_date TEXT, paid_amount_cents INTEGER,
                resulting_renewal_date TEXT, resulting_billing_cycle TEXT,
                resulting_anchor_day INTEGER
            );
            """
        )
        connection.executemany(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (str(uuid4()), "Valid row", 500, "monthly", "2026-04-15", 15, 1),
                (str(uuid4()), "Invalid row", 0, "monthly", "2026-04-15", 15, 1),
            ],
        )
        connection.commit()


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="set SUBSCRIPTIONS_TEST_POSTGRES_URL to run PostgreSQL integration coverage",
)
def test_migration_preserves_data_ids_and_sequence_and_rolls_back_failures(
    tmp_path, monkeypatch
):
    base_url = make_url(POSTGRES_TEST_URL)
    schema = f"test_migration_{uuid4().hex}"
    admin_engine = make_engine(base_url.render_as_string(hide_password=False))
    target_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        scoped_url = base_url.update_query_dict(
            {"options": f"-csearch_path={schema}"}
        ).render_as_string(hide_password=False)
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", scoped_url)
        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
        target_engine = make_engine(scoped_url)

        invalid_source = tmp_path / "invalid.db"
        _create_invalid_source(invalid_source)
        with pytest.raises(MigrationError, match="revirtió los cambios"):
            migrate_sqlite_to_postgres(invalid_source, database_url=scoped_url)
        with target_engine.connect() as connection:
            assert connection.scalar(
                select(func.count()).select_from(SubscriptionRecord.__table__)
            ) == 0

        valid_source = tmp_path / "valid.db"
        subscription_id = _create_valid_source(valid_source)
        preview = migrate_sqlite_to_postgres(
            valid_source, database_url=scoped_url, dry_run=True
        )
        assert (preview.subscriptions, preview.renewals, preview.dry_run) == (1, 1, True)

        report = migrate_sqlite_to_postgres(valid_source, database_url=scoped_url)
        assert (report.subscriptions, report.renewals, report.dry_run) == (1, 1, False)

        repository = SubscriptionRepository(target_engine)
        migrated = repository.get(subscription_id)
        assert migrated is not None
        assert migrated.cost == Decimal("17.99")
        assert migrated.is_active is False
        history = repository.list_renewals(subscription_id)
        assert len(history) == 1
        assert (history[0].renewal_id, history[0].paid_amount, history[0].paid_date) == (
            93,
            Decimal("18.99"),
            date(2026, 4, 1),
        )

        next_payment = repository.confirm_renewal(
            subscription_id,
            scheduled_date=date(2026, 4, 30),
            paid_date=date(2026, 4, 30),
        )
        assert next_payment.renewal_id == 94

        with pytest.raises(MigrationError, match="debe estar vacío"):
            migrate_sqlite_to_postgres(valid_source, database_url=scoped_url)
    finally:
        if target_engine is not None:
            target_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            admin_engine.dispose()


def test_migration_rejects_sqlite_target_and_missing_source(tmp_path):
    missing_source = tmp_path / "missing.db"
    with pytest.raises(MigrationError, match="No existe el archivo"):
        migrate_sqlite_to_postgres(missing_source, database_url="sqlite:///:memory:")

    source = tmp_path / "source.db"
    _create_invalid_source(source)
    with pytest.raises(MigrationError, match="El destino debe ser PostgreSQL"):
        migrate_sqlite_to_postgres(source, database_url="sqlite:///:memory:")

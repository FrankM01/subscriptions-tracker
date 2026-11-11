import sqlite3
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db_models  # noqa: F401 - register ORM metadata
from app.database import Base, make_engine
from app.database_operations import (
    backup_database,
    database_path,
    restore_database,
    validate_database,
)
from app.db_models import RenewalRecord, SubscriptionRecord


def _create_database(path, *, subscription_name: str) -> None:
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        subscription = SubscriptionRecord(
            subscription_id="subscription-1",
            name=subscription_name,
            cost_cents=1299,
            billing_cycle="monthly",
            renewal_date=date(2026, 11, 10),
            anchor_day=10,
            is_active=True,
        )
        subscription.renewals.append(
            RenewalRecord(
                scheduled_date=date(2026, 10, 10),
                paid_date=date(2026, 10, 11),
                paid_amount_cents=1399,
                resulting_renewal_date=date(2026, 11, 10),
                resulting_billing_cycle="monthly",
                resulting_anchor_day=10,
            )
        )
        session.add(subscription)
        session.commit()
    engine.dispose()


def _subscription_data(path):
    engine = make_engine(f"sqlite:///{path}")
    try:
        with Session(engine) as session:
            subscription = session.scalar(
                select(SubscriptionRecord).where(
                    SubscriptionRecord.subscription_id == "subscription-1"
                )
            )
            assert subscription is not None
            return subscription.name, [
                (renewal.paid_date, renewal.paid_amount_cents)
                for renewal in subscription.renewals
            ]
    finally:
        engine.dispose()


def test_database_path_requires_local_file_backed_sqlite():
    assert database_path("sqlite:////tmp/subscriptions.db") == Path(
        "/tmp/subscriptions.db"
    ).resolve()
    for url in (
        "postgresql://localhost/subscriptions",
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file:shared?mode=memory",
        "sqlite:///shared.db?mode=memory",
    ):
        with pytest.raises(ValueError):
            database_path(url)


def test_backup_creates_verified_snapshot_and_refuses_overwrite(tmp_path):
    active = tmp_path / "active.db"
    backup = tmp_path / "backups" / "daily.db"
    _create_database(active, subscription_name="Music")

    assert backup_database(backup, f"sqlite:///{active}") == backup
    assert _subscription_data(backup) == _subscription_data(active)
    with pytest.raises(FileExistsError):
        backup_database(backup, f"sqlite:///{active}")


def test_restore_recovers_subscription_and_history_and_keeps_safety_copy(tmp_path):
    active = tmp_path / "active.db"
    backup = tmp_path / "backup.db"
    _create_database(active, subscription_name="Current name")
    _create_database(backup, subscription_name="Restored name")

    restored_path, safety_copy = restore_database(
        backup, confirm=True, database_url=f"sqlite:///{active}"
    )

    assert restored_path == active
    assert safety_copy is not None and safety_copy.is_file()
    assert _subscription_data(safety_copy) == (
        "Current name",
        [(date(2026, 10, 11), 1399)],
    )
    assert _subscription_data(active) == (
        "Restored name",
        [(date(2026, 10, 11), 1399)],
    )


def test_restore_requires_confirmation_and_rejects_source_equal_to_target(tmp_path):
    active = tmp_path / "active.db"
    _create_database(active, subscription_name="Current")

    with pytest.raises(ValueError, match="confirmación"):
        restore_database(active, confirm=False, database_url=f"sqlite:///{active}")
    with pytest.raises(ValueError, match="no puede ser la base activa"):
        restore_database(active, confirm=True, database_url=f"sqlite:///{active}")
    assert _subscription_data(active)[0] == "Current"


def test_restore_rejects_corrupt_backup_without_touching_active_database(tmp_path):
    active = tmp_path / "active.db"
    corrupt = tmp_path / "corrupt.db"
    _create_database(active, subscription_name="Keep me")
    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises(ValueError):
        restore_database(corrupt, confirm=True, database_url=f"sqlite:///{active}")

    assert _subscription_data(active)[0] == "Keep me"
    assert list(tmp_path.glob("active.db.pre-restore-*.db")) == []


def test_validate_database_rejects_uninitialized_sqlite_file(tmp_path):
    uninitialized = tmp_path / "empty.db"
    with sqlite3.connect(uninitialized):
        pass

    with pytest.raises(ValueError, match="no contiene el esquema"):
        validate_database(uninitialized)

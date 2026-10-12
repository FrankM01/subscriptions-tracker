import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.database import Base, DEFAULT_DATABASE_PATH, get_database_url, make_engine
from app import db_models  # noqa: F401 - register schema metadata
from app.db_models import SubscriptionRecord


PROJECT_ROOT = DEFAULT_DATABASE_PATH.parent.parent


def test_default_database_url_is_project_relative_and_overridable(monkeypatch):
    monkeypatch.delenv("SUBSCRIPTIONS_DATABASE_URL", raising=False)
    assert get_database_url() == f"sqlite:///{DEFAULT_DATABASE_PATH}"

    monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", "sqlite:////tmp/custom.db")
    assert get_database_url() == "sqlite:////tmp/custom.db"


def test_initial_migration_creates_tables_and_constraints(tmp_path, monkeypatch):
    database_path = tmp_path / "nested" / "subscriptions.db"
    monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", f"sqlite:///{database_path}")

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    engine = make_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {
            "alembic_version",
            "subscriptions",
            "renewals",
        }
        assert any(
            fk["options"].get("ondelete") == "CASCADE"
            for fk in inspector.get_foreign_keys("renewals")
        )
        assert {
            constraint["name"]
            for constraint in inspector.get_check_constraints("subscriptions")
        } == {
            "ck_subscriptions_name_nonempty",
            "ck_subscriptions_cost_positive",
            "ck_subscriptions_billing_cycle",
            "ck_subscriptions_anchor_day",
        }
    finally:
        engine.dispose()


def test_sqlite_enforces_checks_foreign_keys_and_cascade(tmp_path):
    database_path = tmp_path / "schema.db"
    engine = make_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        connection.execute(
            text(
                "INSERT INTO subscriptions "
                "(subscription_id, name, cost_cents, billing_cycle, renewal_date, "
                "anchor_day, is_active) VALUES "
                "('sub-1', 'Music', 1299, 'monthly', '2026-11-10', 10, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO renewals "
                "(subscription_id, scheduled_date, paid_date, paid_amount_cents, "
                "resulting_renewal_date, resulting_billing_cycle, resulting_anchor_day) "
                "VALUES ('sub-1', '2026-11-10', '2026-11-10', 1299, "
                "'2026-12-10', 'monthly', 10)"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO subscriptions "
                    "(subscription_id, name, cost_cents, billing_cycle, renewal_date, "
                    "anchor_day, is_active) VALUES "
                    "('invalid', ' ', 0, 'weekly', '2026-11-10', 32, 1)"
                )
            )
        connection.execute(text("DELETE FROM subscriptions WHERE subscription_id='sub-1'"))
        assert connection.scalar(text("SELECT count(*) FROM renewals")) == 0

    engine.dispose()


def test_renewal_lock_statement_compiles_for_postgresql():
    statement = (
        select(SubscriptionRecord.__table__)
        .where(SubscriptionRecord.subscription_id == "sub-1")
        .with_for_update()
    )

    assert "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))

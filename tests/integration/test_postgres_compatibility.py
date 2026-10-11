"""Opt-in integration coverage for PostgreSQL migrations and renewals."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.database import DEFAULT_DATABASE_PATH, make_engine
from app.models.subscription import BillingCycle, Subscription
from app.repositories.subscription_repository import (
    RenewalConflictError,
    SubscriptionRepository,
)


PROJECT_ROOT = DEFAULT_DATABASE_PATH.parent.parent
POSTGRES_TEST_URL = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="set SUBSCRIPTIONS_TEST_POSTGRES_URL to run PostgreSQL integration coverage",
)
def test_postgres_migration_and_renewal_workflows(monkeypatch):
    base_url = make_url(POSTGRES_TEST_URL)
    schema = f"test_subscriptions_{uuid4().hex}"
    admin_engine = make_engine(base_url.render_as_string(hide_password=False))
    test_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

        scoped_url = base_url.update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        scoped_database_url = scoped_url.render_as_string(hide_password=False)
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", scoped_database_url)
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        command.upgrade(config, "head")

        test_engine = make_engine(scoped_database_url)
        inspector = inspect(test_engine)
        assert {"subscriptions", "renewals", "alembic_version"}.issubset(
            set(inspector.get_table_names())
        )
        assert any(
            fk["options"].get("ondelete") == "CASCADE"
            for fk in inspector.get_foreign_keys("renewals")
        )

        repository = SubscriptionRepository(test_engine)
        subscription = Subscription(
            subscription_id=uuid4(),
            name="PostgreSQL integration",
            cost=Decimal("12.50"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=date(2026, 1, 31),
            is_active=True,
        )
        subscription_id = str(subscription.subscription_id)
        repository.add(subscription)

        payment = repository.confirm_renewal(
            subscription_id,
            scheduled_date=date(2026, 1, 31),
            paid_date=date(2026, 1, 31),
        )
        assert payment.paid_amount == Decimal("12.50")
        assert repository.get(subscription_id).renewal_date == date(2026, 2, 28)

        restored = repository.undo_latest_renewal(subscription_id)
        assert restored.renewal_date == date(2026, 1, 31)
        assert repository.list_renewals(subscription_id) == []

        repository.confirm_renewal(
            subscription_id,
            scheduled_date=date(2026, 1, 31),
            paid_date=date(2026, 1, 31),
        )
        assert repository.delete(subscription_id)
        with test_engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM renewals")) == 0

        concurrent_subscription = Subscription(
            subscription_id=uuid4(),
            name="PostgreSQL concurrent confirmation",
            cost=Decimal("8.00"),
            billing_cycle=BillingCycle.monthly,
            renewal_date=date(2026, 3, 15),
            is_active=True,
        )
        concurrent_id = str(concurrent_subscription.subscription_id)
        repository.add(concurrent_subscription)
        start_together = Barrier(2)

        def confirm_same_period():
            start_together.wait()
            try:
                return repository.confirm_renewal(
                    concurrent_id,
                    scheduled_date=date(2026, 3, 15),
                    paid_date=date(2026, 3, 15),
                )
            except RenewalConflictError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: confirm_same_period(), range(2)))

        assert sum(not isinstance(result, RenewalConflictError) for result in results) == 1
        assert sum(isinstance(result, RenewalConflictError) for result in results) == 1
        assert len(repository.list_renewals(concurrent_id)) == 1
    finally:
        if test_engine is not None:
            test_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            admin_engine.dispose()

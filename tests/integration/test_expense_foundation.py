"""Expense migration and constraints on isolated PostgreSQL/SQLite databases."""
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.database import DEFAULT_DATABASE_PATH, make_engine


@pytest.fixture(params=["sqlite", "postgres"])
def expense_database(request, tmp_path, monkeypatch):
    admin = None
    engine = None
    schema = 'test_expense_foundation_' + uuid4().hex
    if request.param == "postgres":
        configured = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")
        if not configured:
            pytest.skip("set SUBSCRIPTIONS_TEST_POSTGRES_URL")
        admin = make_engine(configured)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = make_url(configured).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'expenses.db'}"
    try:
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", url)
        config = Config(str(DEFAULT_DATABASE_PATH.parent.parent / "alembic.ini"))
        command.upgrade(config, "a91e42b7c830")
        engine = make_engine(url)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO subscriptions (subscription_id,name,cost_cents,billing_cycle,renewal_date,anchor_day) VALUES ('prior','Streaming',1990,'monthly','2026-12-13',13)"))
            connection.execute(text("INSERT INTO renewals (subscription_id,scheduled_date,paid_date,paid_amount_cents,resulting_renewal_date,resulting_billing_cycle,resulting_anchor_day) VALUES ('prior','2026-11-13','2026-11-12',2050,'2026-12-13','monthly',13)"))
            connection.execute(text("INSERT INTO utilities (utility_id,name) VALUES ('prior','Luz')"))
            connection.execute(text("INSERT INTO utility_entries (entry_id,utility_id,year,month,amount_cents) VALUES ('prior','prior',2026,11,1234)"))
            connection.execute(text("INSERT INTO debts (debt_id,name,creditor,installment_amount_cents,total_installments,previously_paid_installments,first_due_date) VALUES ('prior','Préstamo','Persona',1000,2,1,'2026-11-13')"))
            connection.execute(text("INSERT INTO debt_installments (installment_id,debt_id,number,amount_cents,due_date) VALUES ('prior','prior',2,1000,'2026-11-13')"))
        command.upgrade(config, "head")
        yield engine, config
    finally:
        if engine is not None:
            engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            admin.dispose()


def test_migration_catalog_and_reversion_preserve_previous_modules(expense_database):
    engine, config = expense_database
    command.check(config)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM expense_categories")) == 6
        assert connection.scalar(text("SELECT count(*) FROM expense_subcategories")) == 6
        assert connection.scalar(text("SELECT count(*) FROM expenses")) == 0
        categories = connection.execute(text("SELECT category_id,name FROM expense_categories ORDER BY name")).all()
    command.downgrade(config, "a91e42b7c830")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT cost_cents FROM subscriptions WHERE subscription_id='prior'")) == 1990
        assert connection.scalar(text("SELECT paid_amount_cents FROM renewals WHERE subscription_id='prior'")) == 2050
        assert connection.scalar(text("SELECT amount_cents FROM utility_entries WHERE entry_id='prior'")) == 1234
        assert connection.scalar(text("SELECT amount_cents FROM debt_installments WHERE installment_id='prior'")) == 1000
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT category_id,name FROM expense_categories ORDER BY name")).all() == categories
        assert connection.scalar(text("SELECT cost_cents FROM subscriptions WHERE subscription_id='prior'")) == 1990
        assert connection.scalar(text("SELECT paid_amount_cents FROM renewals WHERE subscription_id='prior'")) == 2050
        assert connection.scalar(text("SELECT amount_cents FROM utility_entries WHERE entry_id='prior'")) == 1234
        assert connection.scalar(text("SELECT amount_cents FROM debt_installments WHERE installment_id='prior'")) == 1000


def payload(connection):
    category = connection.scalar(text("SELECT category_id FROM expense_categories WHERE name='Alimentación'"))
    subcategory = connection.scalar(text("SELECT subcategory_id FROM expense_subcategories WHERE name='Bebidas'"))
    return {"id": str(uuid4()), "description": "Bebidas", "quantity": 2000, "total": 600,
            "category": category, "subcategory": subcategory}


INSERT = text("INSERT INTO expenses (expense_id,description,quantity_millis,total_amount_cents,expense_date,category_id,subcategory_id) "
              "VALUES (:id,:description,:quantity,:total,'2026-11-01',:category,:subcategory)")


@pytest.mark.parametrize("changes", [
    {"quantity": 0}, {"quantity": 1000000000}, {"total": 0}, {"total": 1000000000},
    {"description": " "}, {"category": "missing"}, {"subcategory": "missing"},
    {"wrong_parent": True},
])
def test_database_rejects_invalid_amounts_quantity_and_classification(expense_database, changes):
    engine, _ = expense_database
    with engine.connect() as connection:
        values = payload(connection)
        if changes.get("wrong_parent"):
            changes = {"category": connection.scalar(text("SELECT category_id FROM expense_categories WHERE name='Transporte'"))}
        values.update(changes)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(INSERT, values)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM expenses")) == 0


def test_exact_storage_optional_subcategory_archive_and_parent_protection(expense_database):
    engine, _ = expense_database
    with engine.begin() as connection:
        values = payload(connection)
        connection.execute(INSERT, values)
        connection.execute(INSERT, {**values, "id": str(uuid4()), "quantity": 125, "subcategory": None})
        connection.execute(text("UPDATE expense_categories SET is_active=false WHERE category_id=:category"), values)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT sum(total_amount_cents) FROM expenses")) == 1200
        assert connection.scalar(text("SELECT quantity_millis FROM expenses WHERE expense_id=:id"), values) == 2000
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM expense_subcategories WHERE subcategory_id=:subcategory"), values)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM expense_categories WHERE category_id=:category"), values)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO expense_categories (category_id,name,name_key) VALUES (:id,'Otra','alimentación')"), {"id": str(uuid4())})

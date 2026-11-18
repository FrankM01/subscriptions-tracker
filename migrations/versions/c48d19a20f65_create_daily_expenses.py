"""Create daily expenses and a two-level editable category catalog.

Revision ID: c48d19a20f65
Revises: a91e42b7c830
"""
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = "c48d19a20f65"
down_revision = "a91e42b7c830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    categories = op.create_table(
        "expense_categories",
        sa.Column("category_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_expense_categories_name"),
        sa.CheckConstraint("length(trim(name_key)) > 0", name="ck_expense_categories_key"),
        sa.UniqueConstraint("name_key", name="uq_expense_categories_key"),
    )
    subcategories = op.create_table(
        "expense_subcategories",
        sa.Column("subcategory_id", sa.String(36), primary_key=True),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.category_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_expense_subcategories_name"),
        sa.CheckConstraint("length(trim(name_key)) > 0", name="ck_expense_subcategories_key"),
        sa.UniqueConstraint("category_id", "name_key", name="uq_expense_subcategories_key"),
        sa.UniqueConstraint("category_id", "subcategory_id", name="uq_expense_subcategories_parent"),
    )
    op.create_index("ix_expense_subcategories_category_id", "expense_subcategories", ["category_id"])
    op.create_table(
        "expenses",
        sa.Column("expense_id", sa.String(36), primary_key=True),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("quantity_millis", sa.Integer(), nullable=False),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("subcategory_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_voided", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.category_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["category_id", "subcategory_id"],
            ["expense_subcategories.category_id", "expense_subcategories.subcategory_id"],
            ondelete="RESTRICT", name="fk_expenses_subcategory_parent",
        ),
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_expenses_description"),
        sa.CheckConstraint("quantity_millis BETWEEN 1 AND 999999999", name="ck_expenses_quantity"),
        sa.CheckConstraint("total_amount_cents BETWEEN 1 AND 999999999", name="ck_expenses_total"),
    )
    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    # Frozen seed data belongs to this revision; future app edits cannot change it.
    for name, children in [
        ("Alimentación", ["Desayuno", "Almuerzo", "Cena", "Bebidas"]),
        ("Transporte", ["Pasajes"]), ("Compras", []), ("Salud", ["Medicinas"]),
        ("Entretenimiento", []), ("Otros", []),
    ]:
        key = name.casefold()
        category_id = str(uuid5(NAMESPACE_URL, "control-budget:expenses:category:" + key))
        op.bulk_insert(categories, [{"category_id": category_id, "name": name, "name_key": key}])
        if children:
            op.bulk_insert(subcategories, [{
                "subcategory_id": str(uuid5(NAMESPACE_URL, "control-budget:expenses:subcategory:" + key + ":" + child.casefold())),
                "category_id": category_id, "name": child, "name_key": child.casefold(),
            } for child in children])


def downgrade() -> None:
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_expense_subcategories_category_id", table_name="expense_subcategories")
    op.drop_table("expense_subcategories")
    op.drop_table("expense_categories")

"""Create fixed monthly debts and their outstanding installments.

Revision ID: a91e42b7c830
Revises: 7b21c9d840ef
"""

from alembic import op
import sqlalchemy as sa

revision = "a91e42b7c830"
down_revision = "7b21c9d840ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debts",
        sa.Column("debt_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("creditor", sa.Text(), nullable=False),
        sa.Column("installment_amount_cents", sa.Integer(), nullable=False),
        sa.Column("total_installments", sa.Integer(), nullable=False),
        sa.Column("previously_paid_installments", sa.Integer(), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_debts_name_nonempty"),
        sa.CheckConstraint("length(trim(creditor)) > 0", name="ck_debts_creditor_nonempty"),
        sa.CheckConstraint("installment_amount_cents > 0", name="ck_debts_amount_positive"),
        sa.CheckConstraint("total_installments > 0", name="ck_debts_total_positive"),
        sa.CheckConstraint(
            "previously_paid_installments BETWEEN 0 AND total_installments",
            name="ck_debts_previous_range",
        ),
        sa.CheckConstraint(
            "(previously_paid_installments < total_installments AND first_due_date IS NOT NULL) "
            "OR (previously_paid_installments = total_installments AND first_due_date IS NULL)",
            name="ck_debts_first_due_date",
        ),
    )
    op.create_table(
        "debt_installments",
        sa.Column("installment_id", sa.String(36), primary_key=True),
        sa.Column("debt_id", sa.String(36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["debt_id"], ["debts.debt_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("debt_id", "number", name="uq_debt_installments_number"),
        sa.CheckConstraint("number > 0", name="ck_debt_installments_number_positive"),
        sa.CheckConstraint("amount_cents > 0", name="ck_debt_installments_amount_positive"),
    )
    op.create_index("ix_debt_installments_debt_id", "debt_installments", ["debt_id"])


def downgrade() -> None:
    op.drop_index("ix_debt_installments_debt_id", table_name="debt_installments")
    op.drop_table("debt_installments")
    op.drop_table("debts")

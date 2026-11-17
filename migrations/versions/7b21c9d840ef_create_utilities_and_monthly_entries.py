"""Create personal utilities and monthly contributions.

Revision ID: 7b21c9d840ef
Revises: 406d989e7e68
"""

from alembic import op
import sqlalchemy as sa

revision = "7b21c9d840ef"
down_revision = "406d989e7e68"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "utilities",
        sa.Column("utility_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_utilities_name_nonempty"),
    )
    op.create_table(
        "utility_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("utility_id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["utility_id"], ["utilities.utility_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("utility_id", "year", "month", name="uq_utility_entries_period"),
        sa.CheckConstraint("year BETWEEN 1900 AND 9999", name="ck_utility_entries_year"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_utility_entries_month"),
        sa.CheckConstraint("amount_cents > 0", name="ck_utility_entries_amount_positive"),
    )
    op.create_index("ix_utility_entries_utility_id", "utility_entries", ["utility_id"])


def downgrade() -> None:
    op.drop_index("ix_utility_entries_utility_id", table_name="utility_entries")
    op.drop_table("utility_entries")
    op.drop_table("utilities")

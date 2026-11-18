"""Loan schedules retain their original day without inventing paid history."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.debt import Debt
from app.services.debt_schedule import build_installments


@pytest.mark.parametrize("first,expected", [
    (date(2025, 1, 31), [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)]),
    (date(2024, 1, 30), [date(2024, 1, 30), date(2024, 2, 29), date(2024, 3, 30)]),
    (date(2025, 12, 29), [date(2025, 12, 29), date(2026, 1, 29), date(2026, 2, 28)]),
])
def test_calendar_preserves_anchor_and_starts_after_declared_progress(first: date, expected: list[date]):
    debt = Debt(debt_id=uuid4(), name="Loan", creditor="Person", installment_amount=Decimal("20.10"),
                total_installments=6, previously_paid_installments=3, first_due_date=first)
    rows = build_installments(debt)
    assert [row.number for row in rows] == [4, 5, 6]
    assert [row.due_date for row in rows] == expected
    assert all(row.paid_date is None and row.debt_id == debt.debt_id for row in rows)
    assert len({row.installment_id for row in rows}) == 3


def test_all_declared_paid_and_calendar_boundary():
    base = dict(debt_id=uuid4(), name="Loan", creditor="Person", installment_amount=Decimal("10"), total_installments=1)
    assert build_installments(Debt.model_validate({**base, "previously_paid_installments": 1})) == []
    rows = build_installments(Debt.model_validate({**base, "first_due_date": date(9999, 12, 31)}))
    assert rows[0].due_date == date(9999, 12, 31)
    with pytest.raises(ValidationError):
        Debt.model_validate({**base, "total_installments": 2, "first_due_date": date(9999, 12, 31)})

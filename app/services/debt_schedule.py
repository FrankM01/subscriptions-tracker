"""Generate only outstanding installments, preserving the original month day."""

from calendar import monthrange
from datetime import date
from uuid import uuid4

from app.models.debt import Debt, DebtInstallment


def build_installments(debt: Debt) -> list[DebtInstallment]:
    first = debt.first_due_date
    if first is None:
        return []
    installments = []
    for offset, number in enumerate(range(
        debt.previously_paid_installments + 1, debt.total_installments + 1,
    )):
        month_index = (first.year - 1) * 12 + first.month - 1 + offset
        year, month = month_index // 12 + 1, month_index % 12 + 1
        due = date(year, month, min(first.day, monthrange(year, month)[1]))
        installments.append(DebtInstallment(
            installment_id=uuid4(), debt_id=debt.debt_id, number=number,
            amount=debt.installment_amount, due_date=due,
        ))
    return installments

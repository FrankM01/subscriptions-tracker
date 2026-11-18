"""Total paid is independent of quantity, with exact decimal contracts."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.expense import ExpenseCategoryCreate, ExpenseCreate
from app.utils.dates import today_in_lima


def test_total_is_not_multiplied_and_fractional_quantities_are_exact():
    expense = ExpenseCreate(description="  Bebidas  ", quantity=Decimal("2"),
                            total_amount=Decimal("6.00"), category_id=uuid4())
    assert expense.description == "Bebidas"
    assert expense.total_amount == Decimal("6.00")
    assert expense.expense_date == today_in_lima()
    assert ExpenseCreate.model_validate({**expense.model_dump(), "quantity": "0.125"}).quantity == Decimal("0.125")
    assert expense.model_dump(mode="json")["total_amount"] == "6.00"
    assert sum(ExpenseCreate(description=name, category_id=uuid4(), total_amount=Decimal(total)).total_amount
               for name, total in [("Almuerzo", "8"), ("Desayuno", "3"), ("Movilidad", "3"), ("Bebidas", "3")]) == Decimal("17")


@pytest.mark.parametrize("changes", [
    {"description": " "}, {"quantity": "0"}, {"quantity": "0.0001"},
    {"quantity": "1000000"}, {"total_amount": "0"}, {"total_amount": "1.001"},
    {"total_amount": "10000000"}, {"total_amount": "NaN"},
    {"expense_date": "1899-12-31"},
    {"expense_date": today_in_lima() + timedelta(days=1)},
    {"unit_price": "3"}, {"category_id": None},
])
def test_invalid_expenses_are_rejected(changes):
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"description": "Gasto", "total_amount": "3.00", "category_id": uuid4(), **changes})


def test_category_names_are_normalized_and_cannot_be_blank():
    assert ExpenseCategoryCreate(name="  Comida   y bebidas  ").name == "Comida y bebidas"
    with pytest.raises(ValidationError):
        ExpenseCategoryCreate(name="  ")

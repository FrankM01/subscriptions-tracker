from datetime import date

import pytest

from app.models.subscription import BillingCycle
from app.services.renewal_calculator import calculate_next_renewal_date


@pytest.mark.parametrize(
    ("current_date", "anchor_day", "expected"),
    [
        (date(2026, 10, 15), 15, date(2026, 11, 15)),
        (date(2026, 12, 31), 31, date(2027, 1, 31)),
        (date(2025, 1, 31), 31, date(2025, 2, 28)),
        (date(2024, 1, 31), 31, date(2024, 2, 29)),
        (date(2025, 2, 28), 31, date(2025, 3, 31)),
    ],
)
def test_monthly_cycle_preserves_anchor(
    current_date: date, anchor_day: int, expected: date
):
    assert (
        calculate_next_renewal_date(current_date, BillingCycle.monthly, anchor_day)
        == expected
    )


@pytest.mark.parametrize(
    ("current_date", "anchor_day", "expected"),
    [
        (date(2024, 2, 29), 29, date(2025, 2, 28)),
        (date(2025, 2, 28), 29, date(2026, 2, 28)),
        (date(2027, 2, 28), 29, date(2028, 2, 29)),
        (date(2025, 10, 31), 31, date(2026, 10, 31)),
    ],
)
def test_yearly_cycle_preserves_anchor(
    current_date: date, anchor_day: int, expected: date
):
    assert (
        calculate_next_renewal_date(current_date, BillingCycle.yearly, anchor_day)
        == expected
    )


@pytest.mark.parametrize("anchor_day", [0, 32, True])
def test_rejects_invalid_anchor_day(anchor_day: int):
    with pytest.raises(ValueError, match="anchor_day must be between 1 and 31"):
        calculate_next_renewal_date(
            date(2026, 10, 15), BillingCycle.monthly, anchor_day
        )


def test_rejects_unsupported_billing_cycle():
    with pytest.raises(ValueError, match="Unsupported billing cycle"):
        calculate_next_renewal_date(date(2026, 10, 15), "weekly", 15)

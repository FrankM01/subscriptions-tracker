"""Pure date calculations for subscription renewal schedules."""

from calendar import monthrange
from datetime import date

from app.models.subscription import BillingCycle


def calculate_next_renewal_date(
    current_date: date,
    billing_cycle: BillingCycle,
    anchor_day: int,
) -> date:
    """Advance one billing period while preserving the original day anchor.

    Short months use their last calendar day. The original anchor is retained
    separately, so a following month or leap year can restore it.
    """
    if isinstance(anchor_day, bool) or not 1 <= anchor_day <= 31:
        raise ValueError("anchor_day must be between 1 and 31")

    if billing_cycle == BillingCycle.monthly:
        if current_date.month == 12:
            year, month = current_date.year + 1, 1
        else:
            year, month = current_date.year, current_date.month + 1
    elif billing_cycle == BillingCycle.yearly:
        year, month = current_date.year + 1, current_date.month
    else:
        raise ValueError(f"Unsupported billing cycle: {billing_cycle!r}")

    day = min(anchor_day, monthrange(year, month)[1])
    return date(year, month, day)

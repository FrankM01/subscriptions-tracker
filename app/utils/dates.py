"""Date helpers for the product's calendar timezone."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


PRODUCT_TIMEZONE = ZoneInfo("America/Lima")


def today_in_lima() -> date:
    return datetime.now(PRODUCT_TIMEZONE).date()

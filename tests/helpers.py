"""Helpers for isolated SQLite repositories in tests."""

from contextlib import contextmanager
from collections.abc import Iterator

from app import db_models  # noqa: F401 - register ORM metadata
from app.database import Base, make_engine
from app.repositories.subscription_repository import SubscriptionRepository
from hypothesis import strategies as st


def valid_name_strategy(max_size: int = 100):
    """Generate names accepted by the current persisted domain constraints."""
    return st.text(min_size=1, max_size=max_size).filter(
        lambda value: bool(value.strip()) and "\x00" not in value
    )


@contextmanager
def temporary_repository() -> Iterator[SubscriptionRepository]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        yield SubscriptionRepository(engine)
    finally:
        engine.dispose()

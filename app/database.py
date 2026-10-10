"""Database configuration and SQLAlchemy engine helpers."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "control_budget.db"


class Base(DeclarativeBase):
    """Base class for persisted domain models."""


def get_database_url() -> str:
    """Return the configured DB URL or the project-local SQLite default."""
    configured_url = os.getenv("SUBSCRIPTIONS_DATABASE_URL")
    if configured_url:
        return configured_url
    return f"sqlite:///{DEFAULT_DATABASE_PATH}"


def make_engine(database_url: str | None = None, **engine_options) -> Engine:
    """Create an engine and enable SQLite foreign key enforcement."""
    url = database_url or get_database_url()
    if url.startswith("sqlite:") and ":memory:" not in url:
        # SQLite does not create missing parent directories for file databases.
        database_path = url.removeprefix("sqlite:///").split("?", 1)[0]
        if database_path and database_path != ":memory:":
            Path(database_path).expanduser().resolve().parent.mkdir(
                parents=True, exist_ok=True
            )

    engine = create_engine(url, **engine_options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine

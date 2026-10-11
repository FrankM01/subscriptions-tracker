"""Validated, transactional import from a SQLite subscriptions database."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sqlite3
from urllib.parse import quote

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app import db_models  # noqa: F401 - register ORM metadata
from app.database import PROJECT_ROOT, get_database_url, make_engine
from app.db_models import RenewalRecord, SubscriptionRecord
from app.database_operations import validate_database


SUBSCRIPTION_COLUMNS = {
    "subscription_id",
    "name",
    "cost_cents",
    "billing_cycle",
    "renewal_date",
    "anchor_day",
    "is_active",
}
RENEWAL_COLUMNS = {
    "renewal_id",
    "subscription_id",
    "scheduled_date",
    "paid_date",
    "paid_amount_cents",
    "resulting_renewal_date",
    "resulting_billing_cycle",
    "resulting_anchor_day",
}


class MigrationError(ValueError):
    """Raised when the source or target is unsafe for a data migration."""


@dataclass(frozen=True)
class MigrationReport:
    subscriptions: int
    renewals: int
    dry_run: bool


def _read_sqlite_source(source: Path) -> tuple[list[dict], list[dict]]:
    """Read a consistent snapshot from a validated, file-backed SQLite DB."""
    validate_database(source)
    quoted_path = quote(str(source), safe="/")
    connection = sqlite3.connect(
        f"file:{quoted_path}?mode=ro", uri=True, timeout=30
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise MigrationError(
                "La base SQLite contiene referencias foráneas inválidas; "
                "corrígelas antes de migrar."
            )

        for table, required in (
            ("subscriptions", SUBSCRIPTION_COLUMNS),
            ("renewals", RENEWAL_COLUMNS),
        ):
            columns = {
                row["name"]
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            missing = required - columns
            if missing:
                raise MigrationError(
                    f"El esquema SQLite de {table} no contiene: "
                    + ", ".join(sorted(missing))
                )

        subscriptions = [
            dict(row)
            for row in connection.execute(
                "SELECT subscription_id, name, cost_cents, billing_cycle, "
                "renewal_date, anchor_day, is_active FROM subscriptions "
                "ORDER BY subscription_id"
            )
        ]
        renewals = [
            dict(row)
            for row in connection.execute(
                "SELECT renewal_id, subscription_id, scheduled_date, paid_date, "
                "paid_amount_cents, resulting_renewal_date, resulting_billing_cycle, "
                "resulting_anchor_day FROM renewals ORDER BY renewal_id"
            )
        ]
    except sqlite3.DatabaseError as exc:
        raise MigrationError(f"No se pudo leer el origen SQLite: {exc}") from exc
    finally:
        connection.close()

    try:
        for row in subscriptions:
            row["renewal_date"] = date.fromisoformat(row["renewal_date"])
            if row["is_active"] not in (0, 1):
                raise ValueError("is_active debe ser 0 o 1")
            row["is_active"] = bool(row["is_active"])
        for row in renewals:
            row["scheduled_date"] = date.fromisoformat(row["scheduled_date"])
            row["paid_date"] = date.fromisoformat(row["paid_date"])
            row["resulting_renewal_date"] = date.fromisoformat(
                row["resulting_renewal_date"]
            )
    except (TypeError, ValueError) as exc:
        raise MigrationError(f"La base SQLite contiene fechas o estados inválidos: {exc}") from exc

    return subscriptions, renewals


def _verify_postgres_target(engine: Engine) -> None:
    """Require a migrated PostgreSQL schema with no application data."""
    if engine.dialect.name != "postgresql":
        raise MigrationError(
            "El destino debe ser PostgreSQL; configura SUBSCRIPTIONS_DATABASE_URL "
            "con una URL postgresql+psycopg."
        )

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    heads = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
        if current_heads != heads:
            raise MigrationError(
                "El esquema PostgreSQL no está actualizado. Ejecuta primero "
                "`.venv/bin/python -m alembic upgrade head`."
            )

        inspector_tables = set(inspect(connection).get_table_names())
        if not {"subscriptions", "renewals"}.issubset(inspector_tables):
            raise MigrationError(
                "El destino PostgreSQL no contiene las tablas de suscripciones."
            )

        subscription_count = connection.scalar(
            select(func.count()).select_from(SubscriptionRecord.__table__)
        )
        renewal_count = connection.scalar(
            select(func.count()).select_from(RenewalRecord.__table__)
        )
        if subscription_count or renewal_count:
            raise MigrationError(
                "El destino PostgreSQL debe estar vacío; no se sobrescribieron datos."
            )


def migrate_sqlite_to_postgres(
    source_path: str | Path,
    *,
    database_url: str | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Copy subscriptions and renewal history into an empty PostgreSQL target.

    The destination schema must already be at the current Alembic head. All data
    writes run in one transaction and roll back together on failure.
    """
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise MigrationError(f"No existe el archivo SQLite de origen: {source}")

    subscriptions, renewals = _read_sqlite_source(source)
    engine = make_engine(database_url or get_database_url())
    try:
        _verify_postgres_target(engine)
        if dry_run:
            return MigrationReport(len(subscriptions), len(renewals), dry_run=True)

        with engine.begin() as connection:
            # Serialize import attempts and application writes before checking
            # emptiness, so competing migrations cannot both pass the guard.
            connection.exec_driver_sql(
                "LOCK TABLE subscriptions, renewals IN SHARE ROW EXCLUSIVE MODE"
            )
            if connection.scalar(
                select(func.count()).select_from(SubscriptionRecord.__table__)
            ) or connection.scalar(
                select(func.count()).select_from(RenewalRecord.__table__)
            ):
                raise MigrationError(
                    "El destino PostgreSQL debe estar vacío; no se sobrescribieron datos."
                )

            if subscriptions:
                connection.execute(SubscriptionRecord.__table__.insert(), subscriptions)
            if renewals:
                connection.execute(RenewalRecord.__table__.insert(), renewals)
                max_renewal_id = max(row["renewal_id"] for row in renewals)
                connection.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence('renewals', 'renewal_id'), "
                        ":max_id, true)"
                    ),
                    {"max_id": max_renewal_id},
                )
    except SQLAlchemyError as exc:
        raise MigrationError(
            "La importación falló y PostgreSQL revirtió los cambios: "
            f"{exc.__class__.__name__}. Revisa el origen y el destino e inténtalo de nuevo."
        ) from exc
    finally:
        engine.dispose()

    return MigrationReport(len(subscriptions), len(renewals), dry_run=False)

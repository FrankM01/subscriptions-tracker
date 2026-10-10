"""Safe local backup and restore operations for the SQLite database."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.parse import quote

from sqlalchemy.engine import make_url

from app.database import get_database_url


REQUIRED_TABLES = {"subscriptions", "renewals"}


def database_path(database_url: str | None = None) -> Path:
    """Resolve the configured SQLAlchemy URL to a file-backed SQLite path."""
    url = make_url(database_url or get_database_url())
    if url.get_backend_name() != "sqlite":
        raise ValueError("La operación solo admite bases SQLite locales.")
    if (
        not url.database
        or url.database == ":memory:"
        or url.database.startswith("file:")
        or url.query.get("mode") == "memory"
    ):
        raise ValueError("La URL debe apuntar a un archivo SQLite local.")
    return Path(url.database).expanduser().resolve()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    quoted_path = quote(str(path), safe="/")
    return sqlite3.connect(f"file:{quoted_path}?mode=ro", uri=True, timeout=30)


def validate_database(path: Path) -> None:
    """Reject missing, corrupt, or uninitialized application databases."""
    if not path.is_file():
        raise ValueError(f"No existe un archivo de base de datos: {path}")
    try:
        with closing(_readonly_connection(path)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise ValueError(f"La base de datos no pasó integrity_check: {result}")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = REQUIRED_TABLES - tables
            if missing:
                raise ValueError(
                    "La base no contiene el esquema de suscripciones; faltan: "
                    + ", ".join(sorted(missing))
                )
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"No se pudo leer la base SQLite {path}: {exc}") from exc


def _copy_database(source: Path, destination: Path) -> None:
    """Create a consistent SQLite snapshot at an already-created empty path."""
    with closing(_readonly_connection(source)) as source_connection:
        with closing(sqlite3.connect(destination, timeout=30)) as destination_connection:
            source_connection.backup(destination_connection)


def _temporary_path(directory: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".sqlite-tmp", dir=directory)
    os.close(descriptor)
    return Path(name)


def _snapshot_to_new_file(source: Path, destination: Path) -> Path:
    """Write a verified snapshot without replacing an existing destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(destination.parent, f".{destination.name}.")
    try:
        _copy_database(source, temporary)
        validate_database(temporary)
        # A hard link publishes the verified file atomically and fails if the
        # destination already exists, unlike os.replace().
        os.link(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
        Path(f"{temporary}-wal").unlink(missing_ok=True)
        Path(f"{temporary}-shm").unlink(missing_ok=True)


def backup_database(
    output_path: str | Path, database_url: str | None = None
) -> Path:
    """Back up the active database, refusing to overwrite any existing file."""
    source = database_path(database_url)
    destination = Path(output_path).expanduser().resolve()
    if source == destination:
        raise ValueError("El archivo de respaldo debe ser distinto de la base activa.")
    validate_database(source)
    return _snapshot_to_new_file(source, destination)


def _safety_backup_path(target: Path) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    return target.with_name(f"{target.name}.pre-restore-{timestamp}.db")


def restore_database(
    input_path: str | Path,
    *,
    confirm: bool,
    database_url: str | None = None,
) -> tuple[Path, Path | None]:
    """Restore a verified backup after snapshotting the current database."""
    if not confirm:
        raise ValueError("La restauración requiere confirmación explícita.")

    source = Path(input_path).expanduser().resolve()
    target = database_path(database_url)
    if source == target:
        raise ValueError("El respaldo de entrada no puede ser la base activa.")
    validate_database(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    safety_backup: Path | None = None
    if target.exists():
        validate_database(target)
        safety_backup = _snapshot_to_new_file(target, _safety_backup_path(target))

    temporary = _temporary_path(target.parent, f".{target.name}.restore-")
    try:
        _copy_database(source, temporary)
        validate_database(temporary)

        if target.exists():
            # The application must be stopped. Checkpoint any WAL and return the
            # active database to rollback-journal mode before swapping its file.
            with closing(sqlite3.connect(target, timeout=30)) as connection:
                mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
                if mode is None or mode[0].lower() != "delete":
                    raise ValueError("No se pudo preparar la base activa para restaurarla.")
            Path(f"{target}-wal").unlink(missing_ok=True)
            Path(f"{target}-shm").unlink(missing_ok=True)

        os.replace(temporary, target)
        return target, safety_backup
    finally:
        temporary.unlink(missing_ok=True)

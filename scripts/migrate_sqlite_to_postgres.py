#!/usr/bin/env python3
"""Safely import a SQLite backup into an empty PostgreSQL database."""

import argparse
from pathlib import Path
import sys

from app.sqlite_to_postgres import MigrationError, migrate_sqlite_to_postgres


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="archivo SQLite o respaldo previamente verificado",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="valida origen y destino sin importar datos",
    )
    args = parser.parse_args()

    try:
        report = migrate_sqlite_to_postgres(args.source, dry_run=args.dry_run)
    except (OSError, MigrationError) as exc:
        parser.error(str(exc))

    action = "Prevalidación completada" if report.dry_run else "Migración completada"
    print(
        f"{action}: {report.subscriptions} suscripciones y "
        f"{report.renewals} renovaciones."
    )
    if report.dry_run:
        print("No se copiaron datos; el destino continúa vacío.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

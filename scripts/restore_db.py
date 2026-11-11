#!/usr/bin/env python3
"""Restore a verified SQLite backup into the active subscriptions database."""

import argparse
from pathlib import Path
import sqlite3
import sys

from app.database_operations import restore_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="respaldo SQLite de origen")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirma el reemplazo de la base local activa",
    )
    args = parser.parse_args()
    try:
        target, safety_backup = restore_database(args.input, confirm=args.confirm)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(f"Base restaurada y verificada: {target}")
    if safety_backup:
        print(f"Copia previa automática: {safety_backup}")
    print("Ejecuta `.venv/bin/python -m alembic upgrade head` antes de iniciar la app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Create a consistent SQLite backup of the active subscriptions database."""

import argparse
from pathlib import Path
import sqlite3
import sys

from app.database_operations import backup_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="archivo nuevo de destino")
    args = parser.parse_args()
    try:
        destination = backup_database(args.output)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(f"Respaldo SQLite creado y verificado: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

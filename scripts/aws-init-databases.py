"""Initialize the two lab databases from an ephemeral ECS task.

Credentials are injected by ECS from Secrets Manager; do not print them.
"""

import os

import psycopg
from psycopg import sql


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    databases = [
        ("subscriptions", required("APP_DB_USER"), required("APP_DB_PASSWORD")),
        ("keycloak", required("KEYCLOAK_DB_USER"), required("KEYCLOAK_DB_PASSWORD")),
    ]
    with psycopg.connect(
        host=required("RDS_HOST"),
        port=5432,
        dbname="postgres",
        user=required("ADMIN_DB_USER"),
        password=required("ADMIN_DB_PASSWORD"),
        sslmode="require",
        connect_timeout=10,
        autocommit=True,
    ) as conn:
        for database, username, password in databases:
            exists = conn.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (username,)
            ).fetchone()
            role_exists = bool(exists)
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
            ).fetchone()
            if exists:
                raise RuntimeError(f"Database {database} already exists; inspect before retrying")
            if not role_exists:
                conn.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(username), sql.Literal(password)
                    )
                )
            else:
                # A previous attempt may have created the role before failing to
                # create its database. Confirm the supplied credential belongs to
                # that role before using it; do not change existing passwords.
                with psycopg.connect(
                    host=required("RDS_HOST"), port=5432, dbname="postgres",
                    user=username, password=password, sslmode="require",
                    connect_timeout=10,
                ):
                    pass
            administrator = required("ADMIN_DB_USER")
            conn.execute(
                sql.SQL("GRANT {} TO {} WITH SET TRUE").format(
                    sql.Identifier(username), sql.Identifier(administrator)
                )
            )
            try:
                conn.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(database), sql.Identifier(username)
                    )
                )
            finally:
                conn.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(username), sql.Identifier(administrator)
                    )
                )
            print(f"Created database {database} and its owner", flush=True)


if __name__ == "__main__":
    main()

"""Run the suite against disposable PostgreSQL without using personal credentials.

Usage: .venv/bin/python -m scripts.run_postgres_tests [pytest arguments...]
Requires Docker. Uses a random loopback port and RAM-backed database storage.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], text=True, capture_output=True, check=check)


def main() -> int:
    name = f"control-budget-tests-{uuid4().hex[:12]}"
    started = False
    try:
        docker(
            "run", "--detach", "--rm", "--name", name,
            "--tmpfs", "/var/lib/postgresql",
            "--publish", "127.0.0.1::5432",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
            "--env", "POSTGRES_DB=control_budget_test", "postgres:18-alpine",
        )
        started = True
        deadline = time.monotonic() + 60
        while True:
            # Probe over TCP: initdb's temporary server uses only a Unix socket.
            ready = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                           "-d", "control_budget_test", check=False)
            if ready.returncode == 0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("PostgreSQL de prueba no estuvo listo en 60 segundos.")
            time.sleep(0.25)
        address = docker("port", name, "5432/tcp").stdout.strip()
        port = int(address.rsplit(":", 1)[1])
        with tempfile.TemporaryDirectory(prefix="control-budget-tests-") as temporary:
            env = os.environ.copy()
            env["SUBSCRIPTIONS_TEST_POSTGRES_URL"] = f"postgresql+psycopg://postgres@127.0.0.1:{port}/control_budget_test"
            env["SUBSCRIPTIONS_DATABASE_URL"] = f"sqlite:///{Path(temporary) / 'app.db'}"
            print("Ejecutando pruebas con PostgreSQL 18 temporal; sin credenciales ni volúmenes personales.", flush=True)
            return subprocess.run(
                [sys.executable, "-m", "pytest", *(sys.argv[1:] or ["-q"])],
                cwd=Path(__file__).resolve().parent.parent, env=env,
            ).returncode
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr)
        return 1
    finally:
        if started:
            stopped = docker("stop", "--time", "1", name, check=False)
            if stopped.returncode != 0:
                raise RuntimeError(f"No se pudo detener el contenedor temporal {name}: {stopped.stderr}")
            print("Contenedor PostgreSQL temporal eliminado.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

# Subscriptions Tracker

## Base de datos local

El proyecto usa SQLite y Alembic. Por defecto, la base se guarda en
`data/control_budget.db`, relativa a la raíz del proyecto. El directorio se crea
automáticamente. Los archivos SQLite están excluidos de Git.

Para elegir otra ubicación, configura `SUBSCRIPTIONS_DATABASE_URL` con una URL
de SQLAlchemy. Por ejemplo:

```sh
export SUBSCRIPTIONS_DATABASE_URL="sqlite:////ruta/absoluta/subscriptions.db"
```

Desde la raíz del proyecto, crea o actualiza el esquema con:

```sh
.venv/bin/python -m alembic upgrade head
```

Para revisar el estado aplicado:

```sh
.venv/bin/python -m alembic current
```

La migración crea `subscriptions` y `renewals`. Los importes persistidos se
guardan en centavos enteros; las renovaciones conservan la fecha programada,
fecha e importe pagados y una copia del calendario resultante para permitir
validar una futura reversión. SQLite aplica las claves foráneas, incluida la
eliminación en cascada del historial al borrar una suscripción.

## Iniciar la API existente

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

La API usa el repositorio SQLite configurado. Ejecuta primero la migración para
que existan las tablas antes de iniciar FastAPI.

## Pruebas

```sh
.venv/bin/python -m pytest -q
```

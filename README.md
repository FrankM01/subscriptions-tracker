# Subscriptions Tracker

## Instalación desde una copia limpia

Desde la raíz del proyecto, crea el entorno e instala las dependencias de la API:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Instala las dependencias de la interfaz una vez:

```sh
cd frontend
pnpm install
cd ..
```

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

## Respaldo y restauración

Detén la API antes de restaurar. Los comandos siguientes se ejecutan desde la
raíz del proyecto y usan la base definida por `SUBSCRIPTIONS_DATABASE_URL` o,
si no está configurada, `data/control_budget.db`.

Crea un respaldo nuevo. El comando verifica la integridad y el esquema SQLite y
no sobrescribe un archivo existente:

```sh
.venv/bin/python -m scripts.backup_db --output "$HOME/Documents/control-budget-backups/subscriptions-$(date +%Y%m%d-%H%M%S).db"
```

Copia los respaldos a otro medio o ubicación para conservarlos si falla el
equipo. Para restaurar, pasa el archivo y confirma explícitamente el reemplazo:

```sh
.venv/bin/python -m scripts.restore_db --input "$HOME/Documents/control-budget-backups/subscriptions-20261010-120000.db" --confirm
.venv/bin/python -m alembic upgrade head
```

Antes de reemplazar una base existente, el comando guarda automáticamente una
copia `*.pre-restore-*.db` junto a la base activa. Si la restauración falla
antes del reemplazo, conserva la base activa. Tras actualizar las migraciones,
puedes iniciar la aplicación normalmente.

## Desarrollo de la aplicación web

En una terminal, desde la raíz del proyecto, inicia la API:

```sh
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

En una segunda terminal, inicia Vite:

```sh
cd frontend
pnpm dev
```

Abre `http://127.0.0.1:5173`. Vite reenvía las llamadas `/subscriptions` a la API local.

## Pruebas del frontend

Desde `frontend/`, ejecuta las pruebas unitarias y el chequeo de tipos:

```sh
pnpm test
pnpm typecheck
```

Para el recorrido de navegador, instala Chromium una vez y ejecuta:

```sh
pnpm exec playwright install chromium
pnpm test:e2e
```

El runner compila la web, inicia FastAPI con una base SQLite temporal en el puerto `8010` y elimina esa base al terminar.

## Servir la aplicación compilada

Desde `frontend/`, compila la web y luego inicia FastAPI desde la raíz:

```sh
pnpm build
cd ..
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

FastAPI sirve la web en `http://127.0.0.1:8000` y la documentación de la API en `/docs`.
El directorio `frontend/dist` se genera con el build y no se versiona.

## Iniciar solo la API

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

La API usa el repositorio SQLite configurado. Ejecuta primero la migración para
que existan las tablas antes de iniciar FastAPI.

## Pruebas

```sh
.venv/bin/python -m pytest -q
```

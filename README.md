# Subscriptions Tracker

## Entorno local con Docker Compose

Docker Compose levanta la app web, PostgreSQL y Keycloak. PostgreSQL guarda la
app y Keycloak en bases y usuarios separados. El volumen `postgres-data`
conserva las bases entre reinicios; los puertos se enlazan solo a `127.0.0.1`.
Esta configuración es para aprendizaje local (`start-dev` de Keycloak), no para
producción.

Desde la raíz del proyecto, crea tu archivo local de configuración y cambia los
valores de ejemplo por contraseñas largas. Usa valores alfanuméricos para evitar
caracteres que deban escaparse dentro de la URL de conexión de la app:

```sh
cp .env.example .env
```

Construye e inicia los tres servicios:

```sh
docker compose up --build
```

La app aplica Alembic automáticamente al iniciar. Luego puedes abrir la app en
`http://127.0.0.1:8000`, OpenAPI en `http://127.0.0.1:8000/docs` y Keycloak en
`http://127.0.0.1:8081` (credenciales definidas en `.env`). Para detenerlos,
usa `Ctrl+C` y luego `docker compose down`; esto conserva los datos. Para borrar
también el volumen local de PostgreSQL y comenzar desde cero, ejecuta
`docker compose down -v`.

Puedes cambiar los puertos anfitrión en `.env` (`APP_HOST_PORT`,
`POSTGRES_HOST_PORT` y `KEYCLOAK_HOST_PORT`). El archivo `.env` y los datos de
la base no se guardan en Git.

Los scripts de inicialización de PostgreSQL se ejecutan únicamente al crear un
volumen vacío. Si cambias nombres/usuarios de las bases luego del primer inicio,
los valores de `.env` no recrearán ni modificarán las bases que ya existen.

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

El proyecto usa SQLite por defecto y Alembic. También admite PostgreSQL. Por defecto, la base se guarda en
`data/control_budget.db`, relativa a la raíz del proyecto. El directorio se crea
automáticamente. Los archivos SQLite están excluidos de Git.

Para elegir otra ubicación, configura `SUBSCRIPTIONS_DATABASE_URL` con una URL
de SQLAlchemy. Por ejemplo:

```sh
export SUBSCRIPTIONS_DATABASE_URL="sqlite:////ruta/absoluta/subscriptions.db"
```

Para PostgreSQL utiliza el driver Psycopg 3 incluido en las dependencias:

```sh
export SUBSCRIPTIONS_DATABASE_URL="postgresql+psycopg://usuario:clave@localhost:5432/subscriptions"
```

La misma migración de Alembic crea el esquema en ambos motores. Las operaciones
de confirmar y deshacer renovaciones conservan la serialización: SQLite toma un
bloqueo de escritura antes de leer; PostgreSQL bloquea la fila de la suscripción
dentro de la transacción.

## Migrar los datos locales a PostgreSQL

Detén la aplicación y crea primero una copia verificada de SQLite con el comando
de respaldo de abajo. Configura `SUBSCRIPTIONS_DATABASE_URL` para apuntar a una
base PostgreSQL vacía. Aplica el esquema y ejecuta primero la prevalidación:

```sh
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m scripts.migrate_sqlite_to_postgres --source /ruta/subscriptions-backup.db --dry-run
```

Si los conteos son correctos, repite el comando sin `--dry-run` para importar.
La herramienta exige un destino vacío y actualizado, conserva IDs, importes,
fechas e historial, y sincroniza la secuencia de renovaciones. Si la importación
falla, revierte todos los cambios del destino; el archivo SQLite queda intacto.
Después puedes iniciar la app usando la URL de PostgreSQL.

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
validar una futura reversión. Ambos motores aplican claves foráneas, incluida
la eliminación en cascada del historial al borrar una suscripción.

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

La integración con PostgreSQL es optativa. Usa una base dedicada para pruebas;
el test crea y elimina un esquema temporal dentro de ella:

```sh
SUBSCRIPTIONS_TEST_POSTGRES_URL="postgresql+psycopg://usuario:clave@localhost:5432/subscriptions_test" \
  .venv/bin/python -m pytest tests/integration -q
```

# Subscription Tracker

Una aplicación web para organizar suscripciones, consultar el gasto mensual
estimado y mantener a la vista los próximos cobros y su historial de renovaciones.

![Resumen de Subscription Tracker con gasto mensual y próximos cobros ficticios](docs/images/resumen.png)

> Las capturas utilizan servicios, importes y fechas ficticios. El proyecto incluye
> un laboratorio personal en AWS con acceso restringido; no hay una demo pública.

## Funcionalidades

- Crear, editar, activar, desactivar y eliminar suscripciones mensuales o anuales.
- Consultar el gasto mensual estimado y los cobros próximos o vencidos.
- Registrar renovaciones y consultar su historial desde el detalle de cada servicio.
- Iniciar y cerrar sesión con Keycloak; la API protege sus rutas con tokens OIDC.
- Persistir datos en SQLite o PostgreSQL y administrar el esquema con Alembic.

<details>
<summary>Ver la lista de suscripciones</summary>

![Lista de tres suscripciones ficticias con precios y fechas de cobro](docs/images/suscripciones.png)

</details>

## Tecnologías y arquitectura

| Área | Tecnologías |
| --- | --- |
| Interfaz | React, TypeScript, Vite |
| API | Python, FastAPI, SQLAlchemy |
| Datos | PostgreSQL, SQLite, Alembic |
| Identidad | Keycloak, OpenID Connect, Authorization Code con PKCE |
| Infraestructura | Docker Compose; laboratorio personal con AWS ECS/Fargate, RDS, ALB y ECR |
| Pruebas | pytest, Vitest, Playwright |

En local, Docker Compose inicia la aplicación, Keycloak y PostgreSQL. La aplicación
y Keycloak utilizan bases y usuarios separados. La API valida los tokens emitidos
por Keycloak y Alembic aplica las migraciones de la aplicación al arrancar.

```text
Navegador → React + TypeScript → FastAPI → PostgreSQL (aplicación)
                    │               ↑
                    └→ Keycloak ────┘
                           └──────────→ PostgreSQL (identidad)
```

El despliegue en AWS es un **entorno personal de aprendizaje**, con acceso
restringido por IP y autenticación. La configuración y herramientas específicas
de ese laboratorio están en esta rama; no se presentan como una demo pública.

## Inicio rápido

**Requisitos:** Docker y Docker Compose.

1. Crea el archivo de configuración y reemplaza las contraseñas de ejemplo:

   ```sh
   cp .env.example .env
   ```

2. Construye e inicia los servicios:

   ```sh
   docker compose up --build -d
   ```

3. Abre la consola de Keycloak en [127.0.0.1:8081](http://127.0.0.1:8081)
   con el administrador definido en `.env`. En el realm `subscriptions`, crea
   un usuario normal y asígnale una contraseña en **Credentials**.
4. Abre la aplicación en [127.0.0.1:8000](http://127.0.0.1:8000) e inicia
   sesión con ese usuario. La documentación de la API está en
   [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Usa `127.0.0.1` en lugar de `localhost`: el realm local permite las redirecciones
para ese origen. Para detener los servicios conservando los datos, ejecuta
`docker compose down`. Los detalles de configuración, pruebas y operación siguen
más abajo.

## Documentación técnica

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

### Realm y usuario de prueba de Keycloak

En el primer inicio, Compose importa el realm definido en
`keycloak/realms/subscriptions-realm.json`. Incluye el cliente público
`subscriptions-web`, Authorization Code con PKCE S256 y el audience mapper para
`subscriptions-api`. Las URLs permitidas corresponden a la app en el puerto
8000 y Vite en el 5173. Keycloak omite la importación si el realm ya existe;
reiniciar el contenedor no sobrescribe los cambios hechos en la consola.

En la consola de Keycloak crea un usuario normal dentro del realm `subscriptions`
y define una contraseña para probar. La app redirige al login al abrirla. Los
tokens viven solo en memoria del navegador; las llamadas a `/subscriptions`
envían un access token Bearer y FastAPI valida firma RS256, expiración, issuer y
audience con las claves públicas de Keycloak. Sin configuración OIDC la API falla
cerrada y responde que la autenticación no está configurada.

La configuración del navegador (`KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_REALM` y
`KEYCLOAK_WEB_CLIENT_ID`) se sirve desde `/auth/config`. La API usa además
`KEYCLOAK_ISSUER_URL`, `KEYCLOAK_JWKS_URL` y `KEYCLOAK_API_AUDIENCE`. El issuer
debe coincidir exactamente con el claim `iss` del token; la URL JWKS debe ser
alcanzable desde el contenedor de la app. Para cambiar el realm o los IDs,
actualiza también el archivo JSON importado. El modo de prueba de la suite usa
una base temporal y desactiva autenticación explícitamente con
`SUBSCRIPTIONS_ENV=test`.

### Preparación de Keycloak para el laboratorio AWS

La imagen para el laboratorio tiene una configuración separada de Compose
local: usa arranque optimizado, PostgreSQL y health checks, e incluye un realm
cuyas URLs se obtienen de variables de entorno. La estimación de Fargate usa
`linux/amd64`; para construir la imagen para esa arquitectura desde la raíz del
proyecto:

```sh
docker build --platform linux/amd64 -f keycloak/aws/Dockerfile -t subscriptions-keycloak-aws:local .
```

En la definición de tarea de ECS deben configurarse al menos:

- `KC_DB_URL_HOST`, `KC_DB_URL_DATABASE`, `KC_DB_USERNAME` y `KC_DB_PASSWORD`:
  conexión a la base de Keycloak. La contraseña debe suministrarse como secreto.
- `KC_HOSTNAME`: URL HTTPS pública de Keycloak, por ejemplo `https://auth.example.com`.
- `KC_HTTP_ENABLED=true` y `KC_PROXY_HEADERS=xforwarded` para terminación TLS en
  el ALB. Permite conexiones a Keycloak solo desde el balanceador y configura
  las direcciones de proxy de confianza apropiadas para la red.
- `KC_BOOTSTRAP_ADMIN_USERNAME` y `KC_BOOTSTRAP_ADMIN_PASSWORD`: credenciales de
  administración inicial suministradas de forma segura.
- `KEYCLOAK_REALM`, `KEYCLOAK_WEB_CLIENT_ID`, `KEYCLOAK_API_AUDIENCE` y
  `KEYCLOAK_APP_ORIGIN`: valores del realm y origen HTTPS de la aplicación, por
  ejemplo `https://app.example.com`, sin barra final ni rutas.

El cliente acepta redirecciones dentro del origen configurado porque el frontend
conserva la URL actual al iniciar sesión; el retorno de logout usa ese origen.
El realm se importa únicamente si aún no existe: cambiar estas variables no
actualiza un realm ya importado. La API debe validar el issuer público exacto y
poder alcanzar el endpoint JWKS. El health check `/health/ready` escucha en el
puerto de gestión 9000; mantenlo accesible solo por la red necesaria para el
balanceador o la comprobación interna.

La imagen `linux/amd64` se desplegó en ECS y se verificaron HTTPS, conexión a
PostgreSQL, login y logout. El servicio es un laboratorio de uso personal;
siguen pendientes mejoras de operación y de verificación del certificado de RDS.

La aplicación también acepta `SUBSCRIPTIONS_DB_HOST`, `SUBSCRIPTIONS_DB_USER` y
`SUBSCRIPTIONS_DB_PASSWORD` para recibir credenciales separadas de Secrets Manager.
Usa PostgreSQL mediante TLS con `sslmode=require`: esta opción cifra la conexión,
pero no verifica la identidad del servidor. `SUBSCRIPTIONS_DATABASE_URL` tiene
prioridad sobre estas variables.

Para verificar una copia cifrada previamente descargada, usa un directorio con la
llave y certificado, y otro con `subscriptions.dump.p7m` y `keycloak.dump.p7m`:

```sh
bash scripts/verify-encrypted-backup.sh ../backups ../backups/2026-11-10
```

El comando pide la contraseña de la llave en la terminal y restaura las copias en
un contenedor PostgreSQL temporal sin red. Conserva la llave privada protegida y
su contraseña: ambas son necesarias para recuperar los datos.

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

El proyecto usa SQLite por defecto y Alembic. También admite PostgreSQL. Por
defecto, la base se guarda en `data/control_budget.db`, relativa a la raíz del
proyecto. El directorio se crea automáticamente. Los archivos SQLite están
excluidos de Git.

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

# Gastos diarios: actualización local G6

Realizada el 18 de noviembre de 2026 (Lima), en macOS con Docker Compose.
Rama `feature/daily-expenses-module`, revisión `14697de`.

## Estado

**G6 completada.** App actualizada en http://127.0.0.1:8000. Respaldo,
restauración, migración y persistencia tras reinicio verificados. El usuario
confirmó acceso con su cuenta habitual a los cuatro módulos, Análisis y
categorías: «Sí, todo abre correctamente».
No se crearon gastos ficticios en su base personal.

| Comprobación | Resultado |
| --- | --- |
| Imagen nueva | Construida antes de pausar la app, con TypeScript y build Vite aprobados |
| Respaldo de subscriptions y keycloak | Creado con app y Keycloak detenidos |
| Restauración PostgreSQL 18 temporal | Conteos, huellas de contenido y secuencias coincidentes en ambas bases |
| Migración personal | `a91e42b7c830` → `c48d19a20f65 (head)` |
| Comparación de esquema | Alembic `check` sin operaciones pendientes |
| Contenido previo de la app | Tablas y secuencias intactas tras migración y reinicio, excepto revisión Alembic esperada |
| Catálogo nuevo | 6 categorías y 6 subcategorías |
| Gastos nuevos | 0 registros antes de la comprobación del usuario |
| Keycloak | Configuración estática de realm, usuarios, credenciales y clientes conservada |
| Reinicio | PostgreSQL, app y Keycloak reiniciados conservando el volumen |
| Disponibilidad | App y PostgreSQL saludables, Keycloak y descubrimiento OIDC disponibles |
| Protección API | `/expenses`, `/expenses/summary`, `/expense-categories` sin token: 401 con Bearer |
| Rutas frontend | `/gastos` y `/gastos/categorias`: HTML 200 |
| Navegador sin sesión | `/gastos` redirige al login real de Keycloak con PKCE S256 |
| Acceso habitual | Usuario confirmó apertura de los cuatro módulos, Análisis y categorías |

## Respaldo verificado

Directorio privado excluido de Git y del contexto Docker:

```text
backups/g6-20261119T001428Z/
  subscriptions.dump
  keycloak.dump
  manifest.json
```

El nombre usa UTC. Directorio con permisos 0700 y archivos 0600. Los dumps
contienen datos personales; el manifiesto registra SHA-256, conteos, huellas
de contenido y estado de secuencias, sin contraseñas ni filas en claro.

Se usó `pg_dump -Fc` con app y Keycloak detenidos. Ambas bases se restauraron
con `pg_restore --exit-on-error --no-owner --no-acl` en PostgreSQL 18 temporal,
sin red ni volumen persistente. Coincidieron las 7 tablas anteriores de la
app y las 100 de Keycloak, además de sus secuencias. El manifiesto marca
`verified_restore: true`; el contenedor temporal se eliminó al terminar.

No se respaldaron roles globales de PostgreSQL; los roles y la configuración
local continúan definidos por `.env` y el inicializador de Compose.

## Actualización y persistencia

```sh
docker compose build app
# Respaldo y restauración verificados antes del siguiente paso.
docker compose up -d --no-build app keycloak
docker compose exec -T app python -m alembic current
```

La imagen aplica Alembic antes de iniciar Uvicorn. Tras migrar se compararon
todos los contenidos y secuencias anteriores de la app contra el respaldo,
excluyendo únicamente `alembic_version`. Se verificó el catálogo inicial y la
ausencia de gastos de prueba.

Después se detuvieron app y Keycloak, se reinició PostgreSQL y se iniciaron
los servicios tras su health check. La comparación de contenido y secuencias
de la app volvió a coincidir. También coincidieron las tablas estáticas de
acceso de Keycloak, incluidos usuarios, credenciales, realm y clientes. Las
tablas operativas de sesiones pueden cambiar al arrancar Keycloak; el respaldo
restaurado completo se comparó antes de la actualización.

El manifiesto conserva `post_migration_verified` y `post_restart_verified`.
No se eliminaron ni recrearon volúmenes. Los servicios personales quedan en
ejecución y los respaldos privados se conservan. No se realizó commit automático.

## Comprobación manual completada

El usuario abrió la app con su sesión habitual de Keycloak y confirmó
Suscripciones, Servicios, Deudas y Gastos diarios, incluidas las vistas Análisis
y Administrar categorías. No se solicitaron ni recibieron sus contraseñas.
El navegador separado usado para verificar la redirección se cerró.

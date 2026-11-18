# Deudas: actualización local D6

Realizada el 17 de noviembre de 2026 en macOS con Docker Compose y la rama
`feature/debts-module`, revisión `b6350f4` (`feat(debts): complete integral flujo`).

## Resultado

**D6 completada.** App actualizada en http://127.0.0.1:8000. El usuario confirmó
login y apertura de Suscripciones, Servicios y Deudas con su cuenta habitual.
No se crearon préstamos ficticios en su base.

| Comprobación | Resultado |
| --- | --- |
| Respaldo de subscriptions y keycloak | Creado antes de migrar, con app y Keycloak pausados |
| Restauración en PostgreSQL 18 temporal | Ambas bases verificadas: conteos, huellas del contenido y secuencias coincidentes |
| Migración | `7b21c9d840ef` → `a91e42b7c830 (head)` |
| Datos anteriores | Contenido y secuencias intactos tras migración y reinicio |
| Deudas tras migración | Tablas vacías antes de la prueba del usuario |
| Reinicio | PostgreSQL, app y Keycloak reiniciados conservando el volumen |
| Disponibilidad | App/PostgreSQL saludables, Keycloak y descubrimiento OIDC disponibles |
| Protección | `/debts` sin token devuelve 401; `/deudas` redirige al login real con PKCE |
| Acceso habitual | Usuario confirmó que puede entrar y abrir los tres módulos |

## Respaldo verificado

Directorio privado, excluido de Git y del contexto de Docker:

```text
backups/d6-20261118T030215Z/
  subscriptions.dump
  keycloak.dump
  manifest.json
```

El nombre usa UTC. Directorio y archivos se crearon con acceso privado para
su propietario. Los dumps contienen datos personales. El manifiesto guarda
SHA-256, conteos y huellas de tablas, estado de secuencias y
`verified_restore: true`, sin contraseñas ni filas en claro.

Se usó `pg_dump -Fc` y se restauraron las copias con `pg_restore --exit-on-error
--no-owner --no-acl` en un contenedor PostgreSQL 18 temporal sin red ni volumen
persistente. No se respaldaron roles globales de PostgreSQL; la conexión y
los roles locales siguen definidos en `.env` y el inicializador de Compose.

Un primer intento del verificador se interrumpió al consultar una secuencia
como registro compuesto. Se corrigió la consulta, se generó un nuevo respaldo
y se verificó su restauración completa antes de migrar. El intento inicial
no modificó la base original.

## Actualización y persistencia

```sh
docker compose up --build -d app keycloak
docker compose exec -T app python -m alembic current
```

La imagen aplica Alembic antes de arrancar Uvicorn. Se confirmó el nuevo head
y se compararon todas las tablas y secuencias anteriores de la app contra el
manifiesto, excluyendo el cambio esperado de `alembic_version`.

Se detuvieron app y Keycloak, se reinició PostgreSQL y se arrancaron los
servicios tras su health check. Se repitió la comparación de datos y secuencias;
también coincidieron realm, usuarios, credenciales y clientes de Keycloak
antes del login del usuario. El volumen `postgres-data` se conservó.

El usuario confirmó: «Sí, puedo entrar y abrir los tres módulos». El navegador
de prueba separado verificó solo la redirección; no recibió contraseñas.

Se añadieron exclusiones de `backups/` en `.gitignore` y `.dockerignore`.
Los servicios personales quedan en ejecución. El navegador de prueba y el
contenedor de restauración se cerraron. El respaldo privado se conserva;
no se publicó ni se creó un commit automático.

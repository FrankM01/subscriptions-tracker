# Gastos diarios: verificación integral G5

Fecha: 18 de noviembre de 2026 (Lima). Rama `feature/daily-expenses-module`.
Código base: `4d602f1`; ampliaciones de pruebas y este informe pendientes de
commit al realizar la verificación.

## Resultado

**G5 aprobada en entornos temporales, sin fallos funcionales encontrados.**
No fue necesario cambiar código de la aplicación. Se añadió un caso de
integración ejecutado en ambos motores, se amplió la prueba de migración y
se añadió un caso frontend de carga/mes vacío del dashboard.

| Comprobación | Resultado |
| --- | --- |
| Suite Python completa con PostgreSQL 18 temporal y SQLite | 366 aprobadas, ninguna omitida |
| Suite frontend Vitest | 64 aprobadas |
| TypeScript y build Vite | Aprobados |
| E2E existentes: Suscripciones y rutas estáticas | 2 aprobadas |
| Chromium → FastAPI → PostgreSQL 18, ciclo completo de gastos | Aprobado |
| Alembic upgrade/check | Sin operaciones pendientes |
| Upgrade/downgrade/upgrade conservando módulos anteriores | Aprobado en SQLite y PostgreSQL |
| Escritorio 1440×960 y móvil 390×844 | Revisados; también sin overflow horizontal a 320 px |
| `git diff --check` | Sin errores |

## Cobertura consolidada

| Área | Evidencia |
| --- | --- |
| Registro | Total independiente de cantidad, cantidad fraccionaria exacta, importe con coma y guardado consecutivo que conserva solo fecha. |
| Validaciones | Importe/cantidad positivos y límites decimales, descripción obligatoria, clasificación válida, fechas desde 1900 sin futuras; error sin perder formulario. |
| Clasificación | Catálogo inicial, creación/renombrado, nombres únicos, padre correcto, archivo/reactivación y conservación de clasificación histórica. |
| Correcciones | Importe, fecha y categoría recalculan agregados; cambiar padre limpia subcategoría; gasto con clasificación archivada admite corregir otros datos. |
| Anulación/restauración | Confirmación explícita, exclusión de todos los totales, restauración de clasificación archivada, conflictos duplicados y bloqueo de edición de anulados. |
| Historial | Orden estable al paginar un mismo día, sin pérdidas/duplicados entre páginas; filtros y búsqueda literal; recuperación al vaciar la última página. |
| Análisis | Total/conteo y agrupaciones reconcilian con el historial completo; sin subcategoría conserva padre; diario y acumulado con días cero, bisiestos y meses actuales/anteriores/futuros. |
| Dashboard | Resumen por fecha real separado de los otros módulos; carga sin ceros inventados, mes vacío y reintento independiente. |
| Persistencia | Milésimas y centavos exactos, datos tras reabrir conexiones y recargar navegador. |
| Transacciones | Competencia entre anular/restaurar, archivo frente a registro y nombres duplicados, con estados válidos. |
| Autenticación | Todas las rutas rechazan solicitudes sin token; ciclo con JWT firmado de prueba, también en PostgreSQL. |
| Migración/regresión | Conserva Suscripciones y su historial de pagos, Servicios y Deudas; catálogo estable al revertir y volver a migrar. |

La nueva integración utiliza 55 gastos de S/ 0.10 con cantidad 0.125, repartidos
en páginas de 50 y 5. Comprueba identificadores únicos, orden repetible y total
exacto S/ 5.50. Corrige uno a S/ 0.25 y cambia clasificación: total S/ 5.65.
Renombrar/archivar su categoría mantiene los importes; moverlo al mes anterior
deja S/ 5.40 y S/ 0.25 respectivamente. Reabrir conexiones, anular y restaurar
conserva cantidad y clasificación.

La migración parte de la revisión de Deudas `a91e42b7c830` con registros en
los tres módulos anteriores. Se verifica la conservación de sus importes,
incluido un pago de Suscripciones, al revertir y volver a aplicar
`c48d19a20f65`. Esta reversión solo se ejecuta en bases desechables.

## Recorrido integrado de navegador

Contenedor `postgres:18-alpine` exclusivo, almacenamiento tmpfs, puerto aleatorio
en loopback y FastAPI en 8012. Todos los registros son ficticios.

1. Registrar almuerzo S/ 8, desayuno S/ 3 (cantidad 0.125), movilidad S/ 3 y
   bebidas S/ 3 (cantidad 2), usando el formulario y «Guardar y agregar otro».
   Verificar total S/ 17, fecha conservada, campos limpiados y persistencia al
   recargar. Importe cero mantiene datos y muestra error; fecha futura falla
   la validación nativa del control.
2. Crear «Pruebas G5», agregar «Compras G5» y renombrarla a «Recargas G5».
   Archivar Alimentación, corregir bebidas a S/ 6.50 manteniendo su clasificación
   original; anular y restaurar desde la UI. Confirmación recibe foco; Análisis
   muestra S/ 20.50 incluso si Movimientos conserva el filtro Anulados.
3. Cambiar bebidas a Transporte: se limpia su subcategoría. Trasladar al
   31 de octubre: octubre S/ 6.50 y noviembre S/ 14.00, contrastados con API.
   Devolver al 15 de noviembre, esperar confirmación de guardado y recargar:
   noviembre S/ 20.50 persistente.
4. Preparar 51 gastos de S/ 0.10 en noviembre de 2025 mediante la API temporal.
   Desde la UI, buscar «Paginación G5», avanzar a página 2 y anular su único
   registro. La app vuelve a página 1 de 1 y Análisis suma S/ 5.00.
5. Preparar Streaming S/ 19.90 mensuales, Luz S/ 35 pendientes y préstamo de
   cuotas S/ 60 en los otros módulos. Anular/restaurar un gasto no cambia sus
   respuestas API. El dashboard mantiene separados esos importes y S/ 20.50
   de gastos diarios.
6. Simular HTTP 503 solo en el resumen de gastos. Los demás bloques siguen
   disponibles; Reintentar recupera S/ 20.50. Abrir Análisis desde su enlace,
   seleccionar Acumulado y desplegar la tabla con Enter. Revisar tabla móvil
   y anchura del documento a 390 y 320 px.
7. Abrir un formulario y archivar su categoría mediante la API para provocar
   un conflicto real HTTP 409. La UI conserva «Conflicto G5» y el importe;
   reactivar y reintentar permite guardarlo. Se anula ese registro auxiliar:
   el análisis vuelve a S/ 20.50.
8. Consultar febrero de 2024 vacío y enero de 2099: estado vacío sin gráficos
   ficticios; el resumen futuro no genera días. Abrir Suscripciones, Servicios
   y Deudas sin errores, reactivar Alimentación y comprobar que una API
   desconocida devuelve 404 JSON.

Una primera espera del recorrido de traslado falló porque se recargó antes
de terminar la confirmación visual del guardado. La API conservó el dato; se
repitió esperando la URL y el registro confirmados, con ambos meses aprobados.
Los errores HTTP 503 y 409 de consola corresponden a las pruebas intencionales.

Capturas locales revisadas (ignoradas por Git):

- `output/playwright/expenses-g5-history-desktop.png`
- `output/playwright/expenses-g5-archived-restored-mobile.png`
- `output/playwright/expenses-g5-dashboard-mobile.png`
- `output/playwright/expenses-g5-table-mobile.png`
- `output/playwright/expenses-g5-analysis-desktop.png`
- `output/playwright/expenses-g5-evolution-desktop.png`
- `output/playwright/expenses-g5-conflict-desktop.png`

## Repetición y límites

```sh
.venv/bin/python -m scripts.run_postgres_tests
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_BROWSERS_PATH=/tmp/control-budget-playwright-browsers pnpm --dir frontend test:e2e
git diff --check
```

El runner PostgreSQL elimina su contenedor al terminar. Los E2E existentes
usan FastAPI/SQLite temporales en 8010; el recorrido de Gastos diarios se hizo
con Playwright CLI y PostgreSQL en 8012, no es un nuevo spec E2E del repositorio.

El navegador usa `SUBSCRIPTIONS_ENV=test`; la protección JWT se comprueba por
separado con claves locales firmadas. No se realizó login real con Keycloak.
No se migró la base personal ni se reconstruyeron sus contenedores. No se
realizó commit automático.

**Siguiente etapa: G6**, respaldar y verificar la restauración antes de
actualizar la app personal; después comprobar acceso real con Keycloak y
persistencia tras reinicio.

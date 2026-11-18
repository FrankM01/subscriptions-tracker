# Deudas: verificación integral D5

Fecha: 17 de noviembre de 2026. Rama `feature/debts-module`.
Revisión base: `ba8d52d` (`feat(debts): add dashboard monthly summary`), con
ampliaciones de pruebas de D5 todavía sin commit al realizar la verificación.

## Resultado

**D5 completada, sin fallos funcionales encontrados.** No fue necesario cambiar
el código de la aplicación. Se añadieron dos casos backend ejecutados en ambos
motores (cuatro comprobaciones) y dos frontend para cubrir huecos de verificación.

| Verificación | Resultado |
| --- | --- |
| Suite Python completa con PostgreSQL 18 temporal y SQLite | 292 aprobadas, ninguna omitida |
| Suite frontend Vitest | 45 aprobadas |
| TypeScript y build Vite | Correctos |
| E2E existentes de suscripciones y rutas | 2 aprobadas |
| Recorrido completo Chromium → FastAPI → PostgreSQL 18 | Aprobado |
| Escritorio 1440×960 y móvil 390×844 | Revisados, sin desbordamiento horizontal en móvil comprobado |
| Alembic upgrade y comparación de esquema PostgreSQL | Correctos, sin diferencias pendientes |
| `git diff --check` | Sin errores |

## Cobertura consolidada

| Área | Evidencia |
| --- | --- |
| Acuerdo y avance previo | Cuotas restantes numeradas después del avance, varios préstamos por acreedor y deuda inicialmente liquidada sin pagos inventados. |
| Calendario | Días 29–31, febrero, año bisiesto, cambio de año y límite del año 9999. |
| Pagos | Cuota completa, prepago, fecha no futura, liquidación y rechazo de confirmación duplicada. |
| Corrección y reversión | Fecha real independiente del vencimiento; reversión explícita recalcula saldo, avance y próxima cuota. |
| Edición | Reconstrucción antes de pagar; bloqueo del acuerdo con pagos confirmados; metadatos siguen editables. |
| Archivo | Conserva obligaciones e historia; pagos y reactivación disponibles. |
| Integridad y transacciones | Restricciones de importe, avance y fecha inicial; numeración única, FK, protección de borrado y rollback completo ante fallos de inserción. |
| Concurrencia | Dos hilos confirmando/deshaciendo; competencia entre reconstrucción y confirmación, sin pérdida de un pago confirmado. |
| Dashboard | Mes de vencimiento separado de fecha real, atrasos anteriores separados, deudas archivadas incluidas y avance declarado excluido. |
| Estados frontend | Carga sin ceros inventados, mes vacío, ausencia de atrasos, conflictos sin perder formulario y reintento independiente. |
| Acceso | Todas las rutas de Deudas rechazan solicitudes sin token; ciclo autenticado con JWT firmado de prueba en PostgreSQL. |
| Persistencia y migraciones | Datos tras reabrir conexiones y recargar navegador; upgrade/check/downgrade en bases temporales conservan datos de módulos anteriores. |
| Regresión | Suites de Suscripciones y Servicios incluidas; recorrido E2E existente de Suscripciones aprobado. |

Los nuevos casos de base verifican directamente que no se puedan insertar
cuotas duplicadas, huérfanas o con monto/número inválido; tampoco se pueden
guardar acuerdos con avance mayor al total, total/importe cero, acreedor vacío
o fecha inicial ausente cuando quedan cuotas. Las operaciones fallidas dejan
intacto el préstamo anterior.

## Recorrido de navegador sobre PostgreSQL

Se inició un contenedor `postgres:18-alpine` exclusivo de prueba, con datos en
tmpfs y puerto aleatorio enlazado a loopback. La app temporal atendió en 8012.

1. Crear «Verificación D5»: 3 cuotas totales, 1 previa declarada, importe S/ 60.50,
   primer vencimiento pendiente 13 de noviembre de 2026. Se generan cuotas 2–3
   y saldo S/ 121.00.
2. Cambiar la cuota a S/ 62.50 antes de pagar. El calendario se reconstruye y
   el saldo queda S/ 125.00.
3. Pagar cuota 2 con fecha 1 de noviembre, antes de su vencimiento. Confirmar
   que Editar deuda ya no muestra campos para modificar el acuerdo.
4. Corregir la fecha real al 2 de noviembre; archivar y reactivar conservando cuotas.
5. Pagar cuota 3 anticipadamente. Tras recargar: 3 de 3, liquidada y saldo S/ 0.00.
6. Cambiar a móvil y abrir Deshacer pago de cuota 2. Comprobar foco en la
   confirmación y cancelación con Tab/Enter. Reabrir y confirmar la reversión.
7. Recargar: deuda pendiente, 2 de 3 pagadas y saldo S/ 62.50. El vencimiento
   pendiente vuelve al 13 de noviembre.
8. Simular una respuesta 503 solo en el resumen de deudas. El dashboard muestra
   error sin afectar Servicios/Suscripciones; Reintentar recupera los datos reales.
9. Comprobar resumen de noviembre: una cuota pendiente por S/ 62.50, cero
   pagadas del mes y sin atrasos de meses anteriores. La cuota de diciembre
   pagada en noviembre no se suma a los vencimientos pagados de noviembre.

Capturas locales revisadas:

- `output/playwright/debts-d5-settled-desktop.png`
- `output/playwright/debts-d5-reopened-mobile.png`
- `output/playwright/debts-d5-retry-mobile.png`
- `output/playwright/debts-d5-dashboard-mobile.png`

El error de consola HTTP 503 durante el reintento es intencional y corresponde
al fallo simulado. La captura de error muestra parte del bloque; el botón se
alcanzó mediante scroll y el reintento se completó.

## Repetición

```sh
.venv/bin/python -m scripts.run_postgres_tests
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_BROWSERS_PATH=/tmp/control-budget-playwright-browsers pnpm --dir frontend test:e2e
git diff --check
```

El runner PostgreSQL crea y elimina su contenedor temporal; no usa volúmenes
ni credenciales personales. El recorrido Chromium de Deudas se realizó con
la herramienta de navegador y datos ficticios; no es un nuevo spec E2E del repositorio.

## Límites y siguiente etapa

El recorrido de navegador usa `SUBSCRIPTIONS_ENV=test`, sin login real. La
protección OIDC se verifica por separado con JWT firmados y PostgreSQL, sin
depender de Keycloak externo. El login real y el reinicio de contenedores
personales se verificaron posteriormente en [D6](deudas-operacion-local.md).

No se ejecutó la migración sobre la base personal ni se reconstruyó su app.
El entorno temporal de navegador y los contenedores de prueba se cerraron
después de verificar. El cierre operativo se completó posteriormente en D6:
respaldo verificado, actualización local, acceso y persistencia tras reinicio.

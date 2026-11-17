# Servicios: verificación integrada S3.4

Fecha: 16 de noviembre de 2026 (Lima).
Rama: `feature/utilities-module`. Código verificado: `6a8e324`.
Resultado: **aprobado en entornos temporales**. No se requirieron correcciones funcionales.

## Pruebas automatizadas

| Comprobación | Resultado |
| --- | --- |
| Suite Python, con PostgreSQL 18 temporal | 232 aprobadas, ninguna omitida |
| Frontend (Vitest) | 30 aprobadas |
| TypeScript y compilación Vite | Correctos |
| E2E existentes de Suscripciones y rutas estáticas | 2 aprobadas |
| `git diff --check` | Sin problemas |

PostgreSQL se ejecutó en un contenedor aislado, con almacenamiento en RAM, puerto
aleatorio y sin credenciales ni volúmenes personales. Las integraciones cubren migraciones,
compatibilidad, restricciones, autenticación de API y escrituras simultáneas. El runner
eliminó el contenedor al terminar.

Las E2E existentes usan FastAPI con SQLite temporal en el puerto 8010; cubren crear,
editar, confirmar/revertir, desactivar/reactivar y eliminar suscripciones, además de
entrada directa a rutas y recursos estáticos. El runner apagó el servidor y eliminó la base.

## Recorrido integrado de Servicios en Chromium

Recorrido adicional mediante Playwright CLI contra FastAPI y SQLite temporal en el puerto
8012. Estos pasos son verificaciones de navegador con aserciones; no forman parte de las
dos E2E existentes del runner. Se utilizaron únicamente datos ficticios.

| Escenario | Resultado observado |
| --- | --- |
| Resumen → Ver servicios → detalle | Conserva el período de Lima (`2026-11`). |
| Falla simulada de resumen de Servicios | Suscripciones sigue visible; Reintentar recupera Servicios. |
| Confirmación con monto cero | Error visible, sin cerrar el formulario. |
| Fecha de pago futura | Control de fecha rechaza el valor fuera del máximo. |
| Confirmar Luz con importe final S/ 46.20 | Resumen: S/ 35.00 pendientes y S/ 71.40 pagados. |
| Recargar directamente el detalle | El pago confirmado sigue presente. |
| Deshacer desde móvil | Resumen: S/ 81.20 pendientes y S/ 25.20 pagados; conserva importe final e historial previo de S/ 40.00. |
| Separación de Suscripciones | Estimación permanece en S/ 19.90 durante confirmación/reversión. |
| Mes sin registros (`2024-01`) | Conteos cero; filtro Pendientes vacío; no genera deuda. |
| Servicio inexistente por URL directa | Mensaje de error y enlace para volver. |
| API desconocida | Respuesta 404 JSON, sin capturarla como documento SPA. |

Los valores del resumen de prueba incluyen un servicio archivado; archivar no borra
sus pendientes ni pagos. Los casos de creación/corrección, pagos históricos entre meses,
archivo/reactivación, duplicados y doble envío también están cubiertos por las pruebas
frontend/backend y por el recorrido de S3.2 registrado en el plan.

Revisión visual a **1440×960** y **390×844**: bloques diferenciados, importes legibles,
navegación móvil accesible y ancho del documento móvil de 390 px, sin desbordamiento.
Capturas locales (ignoradas por Git):

- `output/playwright/qa-services-dashboard-desktop.png`
- `output/playwright/qa-services-dashboard-mobile.png`
- Capturas de formularios y detalle de S3.2 en el mismo directorio.

La prueba de fallo 503 y la ruta inválida producen errores HTTP esperados en la consola;
no representan fallos de la aplicación. El recorrido web usa autenticación desactivada
explícitamente en modo test. La validación JWT está cubierta en la integración PostgreSQL
con claves locales de prueba; no se repitió login/logout contra Keycloak real.

## Reproducción y siguiente etapa

Desde la raíz:

```sh
.venv/bin/python -m scripts.run_postgres_tests
pnpm --dir frontend test
```

Para usar una instalación temporal del navegador:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/control-budget-playwright-browsers pnpm --dir frontend exec playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/tmp/control-budget-playwright-browsers pnpm --dir frontend test:e2e
```

En esta Mac faltaba la revisión Chromium 1248 requerida por el Playwright del proyecto.
Se descargó en `/tmp` y las dos E2E pasaron al reintentarlas. No se cambiaron dependencias
del proyecto para resolverlo. La primera ejecución dentro del sandbox también requirió
permiso para abrir el puerto de prueba.

**Siguiente tarea: S4.1**, respaldar y verificar PostgreSQL local antes de aplicar la
migración y reconstruir la aplicación. La imagen que atiende el puerto 8000 y la base
personal no se modificaron durante S3.4. La actualización local, persistencia tras reinicio
y comprobación del acceso con Keycloak corresponden al cierre operativo S4.

## Ampliación posterior: suscripciones ya pagadas

Tras la verificación anterior se añadió la creación de suscripciones con pago inicial.
Se reejecutó la regresión: **244 pruebas Python con PostgreSQL 18 y ninguna omitida,
33 frontend, TypeScript/build y 2 E2E existentes aprobadas**. La evidencia de esta
ampliación está en [Suscripciones: pago inicial](suscripciones-pago-inicial.md).
Los resultados de las secciones anteriores documentan la revisión original de `6a8e324`.

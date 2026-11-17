# Suscripciones: registrar un período ya pagado

Solicitud del 16 de noviembre de 2026: permitir crear una suscripción cuyo pago del mes
ya se realizó, conservando ese pago en el historial.

## Uso

1. Abrir **Suscripciones → Nueva suscripción** e ingresar nombre, precio y frecuencia.
2. Activar **Ya pagué este período**.
3. Indicar **Fecha del cobro ya pagado**: la fecha programada del período que se pagó.
4. Revisar **Fecha real del pago** e **Importe pagado**, precargados con hoy en Lima y
   el precio de la suscripción. Se pueden cambiar de forma independiente.
5. Guardar. El pago queda en el historial y la próxima fecha avanza exactamente un ciclo.

Ejemplo mensual: cobro previsto el 1 de noviembre, pagado el 3 de noviembre por S/ 19.90,
precio recurrente S/ 20.00. Se guarda ese pago y el próximo cobro queda el 1 de diciembre.

Sin esta opción se conserva la creación pendiente y su fecha futura obligatoria. La
opción aparece solo al crear; los pagos siguientes se registran desde el detalle con
Confirmar cobro. El pago inicial admite Deshacer último con las reglas existentes.

## Datos y comportamiento

Se amplía `POST /subscriptions` con el campo opcional `initial_payment`:

```json
{
  "name": "Música",
  "cost": "20.00",
  "billing_cycle": "monthly",
  "renewal_date": "2026-11-01",
  "initial_payment": {
    "paid_date": "2026-11-03",
    "paid_amount": "19.90"
  }
}
```

Cuando existe `initial_payment`, `renewal_date` identifica la fecha programada del cobro
pagado; la respuesta devuelve la siguiente fecha pendiente. `initial_payment: {}` usa
hoy en Lima y el precio como valores reales del pago. Omitir el campo o enviarlo como
null mantiene el contrato anterior de creación pendiente con fecha futura.

- Suscripción, pago y avance se guardan en una única transacción. Una falla del historial
  revierte también la creación, sin dejar una suscripción a medias.
- Se reutilizan las tablas y el historial de renovaciones actuales; no hay migración nueva.
- Fecha real de pago no futura; importe pagado positivo, hasta dos decimales y máximo
  S/ 9,999,999.99. El precio recurrente y el importe histórico son independientes.
- Próximo cobro calculado desde la fecha programada, preservando día ancla en meses
  cortos y años bisiestos. Se admite pagar antes de la fecha programada.
- Se avanza un único mes/año; cargar un pago antiguo no inventa los pagos intermedios y
  puede dejar un siguiente cobro vencido. Ese caso se conserva como pendiente real.
- Es posible crear una suscripción inactiva con su primer pago; conserva el historial y
  sigue excluida de estimaciones/avisos según las reglas existentes.
- Deshacer el primer pago elimina su entrada y restaura la fecha programada original.
- Fechas que excederían el calendario al avanzar devuelven 422 sin crear registros.

## Verificación

- **244 pruebas Python aprobadas con PostgreSQL 18**, ninguna omitida: 12 pruebas nuevas
  cubren pago del mes actual, valores por defecto, fin de mes/ancla, año bisiesto, estado
  inactivo, prepago, validaciones, compatibilidad y rollback de la creación completa.
- La integración autenticada existente se amplió para comprobar creación pagada y
  reversión contra PostgreSQL real con JWT de prueba.
- **33 pruebas frontend aprobadas**, TypeScript y build correctos. Tres pruebas nuevas
  verifican fechas e importes independientes, desactivar la opción sin enviar pago inicial,
  fecha futura inválida y ausencia de esta opción al editar.
- **2 E2E existentes aprobadas**: regresión del flujo normal de Suscripciones y rutas.
- Revisión del formulario en Chromium, escritorio/móvil, con API y base SQLite temporales.
  El interruptor permite clic directo y por etiqueta; campos/botones se bloquean al guardar.
- Recorrido real: período del 1 de noviembre de 2026, pago del 3 de noviembre por S/ 19.90,
  precio recurrente S/ 20.00; historial guardado y próxima fecha 1 de diciembre de 2026.
  Persistencia comprobada al recargar. Capturas locales en `output/playwright/`.
- Detector visual sobre el formulario sin hallazgos. `git diff --check` sin problemas.

El código corresponde a `feature/utilities-module`. No se reconstruyó la app Docker
ni se modificaron bases personales. El cierre operativo sigue pendiente de respaldo y
actualización local según el plan del módulo Servicios.

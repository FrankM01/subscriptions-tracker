# Deudas: interfaz D3

Implementada el 17 de noviembre de 2026 en `feature/debts-module`.

## Uso

1. Abrir **Deudas** desde el menú lateral o la navegación móvil.
2. Elegir **Nueva deuda** e indicar nombre, acreedor e importe mensual acordado.
3. Ingresar el total de cuotas y las pagadas antes de usar la aplicación.
4. Indicar el primer vencimiento pendiente. Por ejemplo, 1 cuota pagada de 6
   con primer vencimiento el 31 de enero genera las cuotas 2–6 desde esa fecha.
5. Guardar para abrir el detalle y consultar avance, saldo y calendario.

Las cuotas previas se muestran como avance declarado, sin fechas o pagos
inventados. Si el avance cubre todas las cuotas, el formulario no pide fecha
y crea la deuda liquidada, sin calendario pendiente.

La lista permite buscar por nombre o acreedor y filtrar activas, archivadas,
con saldo, vencidas o liquidadas. El mes opcional selecciona deudas con alguna
cuota que vence en ese mes; los importes y el avance siguen siendo del acuerdo
completo. El detalle permite filtrar también las cuotas pendientes o pagadas.

## Pagos y edición

- **Pagar cuota N** registra el importe completo con la fecha real indicada,
  que puede ser anterior al vencimiento. No admite fecha futura ni abonos parciales.
- **Corregir fecha de cuota N** modifica la fecha de un pago confirmado.
- **Deshacer pago de cuota N** requiere confirmar **Volver a pendiente**.
  Conserva vencimiento e importe y recalcula avance y saldo.
- **Editar deuda** permite ajustar el acuerdo mientras no haya pagos confirmados.
  Con pagos existentes muestra el acuerdo bloqueado y permite solo nombre,
  acreedor y notas. La API sigue validando esta restricción ante cambios simultáneos.
- **Archivar deuda** conserva sus cuotas, saldo y pagos; se pueden seguir pagando.
  **Reactivar deuda** conserva el calendario existente.

Los errores se muestran sin perder el formulario. Mientras se guarda se
bloquean sus campos y botones para evitar dobles envíos. Tras guardar se
recarga el detalle, incluyendo los identificadores nuevos si se reconstruyó
el calendario. La confirmación de reversión recibe foco para hacerla visible.

## Integración

Rutas frontend `/deudas` y `/deudas/:debtId`, con carga directa y recarga desde
FastAPI. El parámetro `period=YYYY-MM` conserva el mes al entrar y volver del
detalle. Cliente TypeScript con los contratos del backend y el mismo manejo
de tokens y errores del resto de módulos. Vite redirige `/debts` a la API local.

La navegación móvil tiene cuatro destinos. Se reutilizan los componentes y
estilos visuales existentes, con formularios en la página y campos apilados
en pantallas pequeñas. El dashboard de deudas queda pendiente de D4.

## Verificación

- **40 pruebas frontend aprobadas**, incluidas 7 nuevas para navegación y filtros,
  creación con avance previo, conflictos y bloqueo durante guardado, acuerdo
  con pagos, corrección y reversión explícita, reactivación y recuperación de errores.
- **288 pruebas Python aprobadas con PostgreSQL 18 temporal**, ninguna omitida.
  La prueba de rutas incluye carga directa de `/deudas` y detalle, conservando
  respuestas JSON 404 en rutas API desconocidas.
- TypeScript y build Vite correctos; **2 E2E existentes aprobadas**.
- Chromium con API y SQLite temporales: creación con 1 de 6 pagadas y cuotas
  de S/ 100.25; calendario 31 de enero, 28 de febrero, 31 de marzo; saldo S/ 501.25.
  Pago anticipado de la cuota 2, persistencia al recargar y saldo S/ 401.00;
  corrección de fecha, reversión confirmada y saldo restablecido a S/ 501.25.
  Archivo comprobado con deuda y obligaciones presentes en la lista.
- Revisión visual en escritorio 1440×960 y móvil 390×844: detalle, calendario,
  lista y formulario. Sin desbordamiento horizontal en las vistas comprobadas.
  Capturas en `output/playwright/debts-*.png`. La captura móvil de página completa
  repitió capas fijas del navegador; se reemplazó por capturas de viewport por secciones.
- Detector de diseño sin hallazgos en los tres componentes nuevos; revisión
  visual independiente sobre capturas y código. `git diff --check` sin problemas.

No se reconstruyeron los contenedores personales ni se modificó su base.
El cierre operativo requiere respaldo y actualización local en D6.

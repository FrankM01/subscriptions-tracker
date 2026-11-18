# Deudas: préstamos con cuotas mensuales

## Alcance acordado

Un préstamo pertenece a una persona o acuerdo; una misma persona puede tener varios.
Se registra nombre, acreedor, importe de la cuota en PEN, número total de cuotas,
cuotas previamente pagadas, primer vencimiento pendiente y notas opcionales.
Ejemplo: 6 cuotas totales y 1 ya pagada generan únicamente las cuotas 2 a 6.
El avance previo es declarado: no inventa fechas ni movimientos de dinero.

El calendario es mensual y fijo. La primera fecha pendiente define el día ancla;
los meses cortos usan su último día y los siguientes recuperan el día original.
Puede empezar en una fecha vencida. Si todas las cuotas ya fueron pagadas,
no se requiere primer vencimiento ni se generan cuotas pendientes.

Cada cuota admite un pago completo, anticipado o vencido, con fecha real de pago
no posterior a hoy en Lima. Se permite corregir esa fecha y deshacer una
confirmación. No hay pagos parciales, cálculo de intereses ni refinanciación.
El importe es el ya acordado con el acreedor.

El calendario y el importe pueden corregirse mientras no existan pagos
confirmados en la aplicación. Después solo se editan nombre, acreedor y notas.
Archivar o reactivar conserva el calendario y los pagos; archivar no elimina
obligaciones pendientes. El saldo se calcula con las cuotas restantes, sin
persistir contadores duplicados. Una deuda queda liquidada al completar sus cuotas.

## Implementación por etapas

- [x] D0: documentar alcance y crear rama `feature/debts-module`.
- [x] D1: contratos, tablas, migración aditiva y generador de calendario.
- [x] D2: repositorio y servicio transaccionales; API autenticada `/debts`.
- [x] D3: pantalla de deudas, detalle, calendario y formularios.
- [x] D4: resumen del mes en dashboard y vencidos anteriores separados.
- [x] D5: verificación PostgreSQL, frontend, navegación y móvil.
- [ ] D6: respaldo y actualización local con Docker Compose.

D2 incluye creación atómica, listado/detalle, edición del acuerdo según sus
pagos, archivo/reactivación, confirmación única por cuota, corrección de fecha,
deshacer pago y resumen mensual. Los bloqueos y transacciones deben impedir
confirmaciones duplicadas y cambios simultáneos de calendario y pagos.

D3 agrega Deudas a la navegación existente y muestra avance, saldo, próximo
vencimiento, atrasos y el historial real de pagos. D4 suma por fecha de
vencimiento e incluye deudas archivadas. Las fechas reales de pago se conservan
para un futuro registro financiero; este módulo no calcula ingresos ni saldo
bancario y no mezcla sus importes con las estimaciones de suscripciones.

## Validación

Verificar 1 de 6 pagadas, cero pendientes, varios préstamos por acreedor,
importes inválidos, numeración única, días 29–31, años bisiestos y límite del
calendario. La migración debe conservar suscripciones y servicios y permitir
volver a la revisión anterior sin borrar sus datos.

En D2–D5: pagos anticipados y vencidos, duplicados y concurrencia, liquidación,
corrección, deshacer, restricciones de edición y archivo con historia. Ejecutar
regresión con PostgreSQL temporal y probar escritorio y móvil antes de D6.

## Estado del trabajo

Inicio: 2026-11-17. El trabajo de suscripciones con pago inicial se guarda en
un commit separado de `feature/utilities-module`, incorporado como base de esta
rama. No se publican cambios. D1 no modifica la base de datos personal ni levanta
contenedores personales. La API de D2 y la interfaz de D3 están implementadas;
el resumen del dashboard de D4 también está implementado. Contrato: [API de deudas](deudas-api.md).
Interfaz y verificación: [Deudas D3](deudas-interfaz.md).
Verificación integral D5: [Resultados y límites](deudas-verificacion.md).

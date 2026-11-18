# Deudas: API y verificación D2

Implementado el 17 de noviembre de 2026 en `feature/debts-module`.
Todos los endpoints usan la autenticación OIDC existente. Los datos son
personales, importes en PEN y fechas de pago según America/Lima.

## Crear un préstamo

`POST /debts` devuelve 201 con acuerdo, calendario, avance y saldo calculados:

```json
{
  "name": "Préstamo personal",
  "creditor": "Persona",
  "installment_amount": "100.25",
  "total_installments": 6,
  "previously_paid_installments": 1,
  "first_due_date": "2026-12-13",
  "notes": "Cuota acordada para el día 13"
}
```

Genera cuotas 2–6 desde el 13 de diciembre; avance 1 de 6 y saldo S/ 501.25.
No se genera una transacción por la cuota previa declarada. Se permite más
de un préstamo por acreedor, fechas iniciales vencidas y deudas ya liquidadas:
en estas últimas las cuotas previas igualan al total y `first_due_date` es null.

## Endpoints

| Método y ruta | Comportamiento |
| --- | --- |
| `GET /debts` | Lista todos los préstamos; filtro opcional `is_active=true/false`. |
| `GET /debts/{id}` | Acuerdo, cuotas ordenadas por número, avance y saldo. |
| `PATCH /debts/{id}` | Edición parcial, archivo o reactivación con `is_active`. |
| `GET /debts/{id}/installments` | Calendario de cuotas pendientes y pagadas. |
| `POST /debts/{id}/installments/{cuota}/confirm` | Pago completo; `{}` usa hoy en Lima, o enviar `paid_date`. |
| `PATCH /debts/{id}/installments/{cuota}` | Corregir `paid_date` de una cuota confirmada. |
| `POST /debts/{id}/installments/{cuota}/undo` | Deshacer el pago, conservando número, vencimiento e importe. |
| `GET /debts/summary?year=2026&month=12` | Conteos e importes pendientes/pagados por mes de vencimiento. |

Los detalles incluyen `paid_installments`, `pending_installments`,
`remaining_balance`, `next_due_date`, `overdue_installments`, `status`
(`pending`/`settled`), `schedule_editable` e `installments`.
Los importes JSON se devuelven como cadenas decimales.

No se admite cambiar importes desde la confirmación ni realizar pagos parciales.
La fecha real puede ser anterior al vencimiento, pero no posterior a hoy.
Se puede pagar cualquier cuota sin exigir orden; el próximo vencimiento es
la menor fecha todavía pendiente. Una cuota que vence hoy no se considera vencida.

## Edición y transacciones

Mientras no haya pagos confirmados, cambiar importe, total, avance previo o
primera fecha reconstruye las cuotas pendientes dentro de una sola transacción.
Esta reconstrucción reemplaza sus identificadores; recargar el detalle después
de editar. Los días 29–31 se conservan como ancla a través de meses cortos.

Con pagos confirmados se bloquean cambios efectivos del calendario/importe
(409); nombre, acreedor, notas y archivo siguen disponibles. Deshacer todos
los pagos vuelve a habilitar la corrección. El acuerdo resultante se valida
completo antes de escribir, aunque el PATCH incluya solo algunos campos.
Las notas pueden limpiarse con null; los demás campos obligatorios no.

Creación y reconstrucción revierten todos sus cambios si falla la inserción
de cuotas. Toda edición y pago bloquea el mismo préstamo: PostgreSQL usa
`FOR UPDATE`; SQLite inicia `BEGIN IMMEDIATE` antes de leer. Una doble
confirmación o reversión devuelve un éxito y un conflicto, sin pagos duplicados.

La API devuelve 404 para deuda/cuota inexistente o cuota de otra deuda,
409 para conflictos de estado, 422 para entrada inválida y 500 con un mensaje
público sin SQL para fallas de almacenamiento. No se exponen rutas de borrado.

## Resumen mensual

Los totales se agrupan por vencimiento, independientemente de la fecha real
del pago. Incluyen deudas archivadas y excluyen el avance previo declarado.
`overdue_before_month_count` y `total_overdue_before_month` separan cuotas
pendientes anteriores al mes consultado que ya estén vencidas hoy en Lima;
no incluyen cuotas del mes seleccionado ni obligaciones futuras.
El resumen se calcula en una única consulta para mantener conteos e importes
en la misma vista de los datos.

## Verificación

- Regresión completa: **286 pruebas Python aprobadas**, ninguna omitida,
  con PostgreSQL 18 temporal y SQLite; incluye 38 casos API/transacciones y
  4 casos de calendario nuevos.
- Dos comprobaciones adicionales verifican errores públicos ante un esquema
  ausente, una por configuración de motor del fixture.
- Se verifican avance previo, liquidación, prepago, archivo, persistencia al
  reabrir conexiones, corrección de fecha y deshacer, además de días ancla,
  año bisiesto y límite del calendario.
- Pruebas con dos hilos comprueban confirmaciones/reversiones simultáneas y
  competencia entre cambios del acuerdo y confirmación.
- Se provoca un fallo de inserción para comprobar rollback completo tanto
  al crear el préstamo como al reemplazar su calendario.
- Autenticación comprobada en todas las rutas sin token y ciclo con JWT
  firmado de prueba. Se rechazan tokens inválidos; no requiere Keycloak real.
- Alembic `upgrade`, `check` y `downgrade` verificados en bases temporales;
  la reversión de deudas conserva servicios existentes. Se actualizó la
  prueba anterior del esquema para incluir las dos tablas nuevas.

No se ha migrado la base personal ni reconstruido la aplicación local.
La interfaz corresponde a D3; el dashboard a D4. No hay cambios frontend en D2.

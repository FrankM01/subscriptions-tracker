# Servicios: alcance, decisiones y tareas

Fecha: 16 de noviembre de 2026. Relacionado en Obsidian: [[Proyecto - Control Budget]].

## Objetivo y alcance

Registrar únicamente mi aporte personal de luz, agua, internet, gas y otros servicios
de una vivienda. Conservar el historial mensual y distinguir lo pendiente de lo pagado.
La app seguirá utilizándose localmente en macOS mediante Docker Compose, PostgreSQL,
Keycloak y FastAPI con el frontend React, en http://127.0.0.1:8000.

Ejemplo: Luz, noviembre de 2026, mi monto S/ 45.00, pendiente; al confirmar se guarda
la fecha real del pago. El monto puede ajustarse al confirmar.

## Decisiones acordadas

- Primera entrega: servicios e historial. Ingresos y saldo financiero quedan después.
- Se ingresa directamente mi monto; no se calcula el reparto ni se registran terceros.
- Cada servicio tiene un registro por mes/año y un único pago completo por período.
- Registrar nuevos meses manualmente, mostrando el último pago como referencia.
  No copiar importes ni generar deudas automáticamente.
- Se permiten pendientes y carga directa de pagos históricos.
- Sin adjuntos ni abonos parciales. Moneda PEN, fechas según America/Lima.
- Archivar servicios conserva sus pendientes e historial; se permite reactivarlos.
- Permitir corregir registros y deshacer confirmaciones accidentales.
- El período corresponde al servicio; la fecha de pago corresponde al desembolso.
  Pagar noviembre en diciembre no cambia el período de noviembre.
- Uso personal: conservar la autenticación existente; no introducir gestión multiusuario.

## Modelo y contratos iniciales

`utilities`: UUID, nombre obligatorio, proveedor opcional y estado activo/archivado.

`utility_entries`: UUID, servicio, año (1900–9999), mes (1–12), mi monto en céntimos,
vencimiento opcional, fecha de pago opcional y notas opcionales. Restricción única por
servicio/año/mes; monto positivo; clave foránea restringe borrar un servicio con historial.

La fecha de pago determina el estado: ausente = pendiente; presente = pagado.
El importe representa mi aporte previsto mientras está pendiente y el importe final
al pagarlo; no es el costo total del hogar. No se duplican estados ni movimientos
contables en esta etapa. Al deshacer un pago se borra su fecha y se conserva el importe.

Los contratos Pydantic iniciales son `UtilityCreate`, `Utility`, `UtilityEntryCreate`
y `UtilityEntry`. Importes decimales serializados como cadenas; máximo 9 dígitos y
2 decimales para caber en el entero de céntimos de PostgreSQL. Rechazar pagos futuros,
nombres vacíos, meses inválidos, montos no positivos y campos ajenos al contrato.

API prevista, todavía no implementada: catálogo y registros bajo `/utilities`, con
detalle, edición/archivo, historial, confirmación/reversión y resumen mensual;
autenticación OIDC existente. El catálogo no tendrá eliminación permanente en v1.

## Experiencia prevista

- Navegación «Servicios» en escritorio y móvil, con la identidad visual actual.
- Vista mensual: selector de período, pendientes/pagados y totales personales.
- Detalle por servicio con historial, último pago como referencia y formularios.
- Formulario de registro con mes/año, mi monto, vencimiento y notas opcionales.
- Confirmar con fecha de hoy e importe precargados, ambos editables.
- Resumen principal: bloque de servicios del mes separado de la estimación de suscripciones.
- Futuro saldo: calcular gastos por fecha efectiva, no por estimaciones o pendientes.

## Tareas

- [x] **S0.1** Acordar alcance y documentar decisiones y tareas.
- [x] **S1.1** Añadir modelos SQLAlchemy de servicios y registros mensuales.
- [x] **S1.2** Añadir migración aditiva y reversible, sin modificar las tablas existentes.
- [x] **S1.3** Definir contratos iniciales y validaciones Pydantic.
- [x] **S1.4** Verificar migración, restricciones, persistencia y regresión en SQLite temporal; registrar resultados. PostgreSQL real pendiente en S2.3/S4.
- [ ] **S2.1** Implementar repositorio y servicio: catálogo, archivo/reactivación e historial.
- [ ] **S2.2** Implementar registro mensual, corrección, confirmación y reversión transaccionales.
- [ ] **S2.3** Exponer endpoints autenticados y resumen mensual; probar errores y concurrencia.
- [ ] **S3.1** Añadir cliente API, tipos TypeScript y navegación «Servicios».
- [ ] **S3.2** Implementar vista mensual, detalle, formularios y estados de carga/error/vacío.
- [ ] **S3.3** Integrar bloque mensual en Resumen sin mezclar previsión con pagos reales.
- [ ] **S3.4** Probar flujo completo y revisar visualmente en escritorio y móvil.
- [ ] **S4.1** Respaldar PostgreSQL local antes de aplicar la migración.
- [ ] **S4.2** Reconstruir contenedores locales y comprobar migración y persistencia tras reinicio.
- [ ] **S4.3** Actualizar README y cerrar checklist con evidencia.

## Validación

Pruebas de esta primera etapa en bases temporales: upgrade desde esquema anterior
con suscripciones y renovaciones existentes, Alembic sin diferencias contra ORM,
downgrade que conserva datos anteriores, archivo y reapertura que conservan historial,
duplicados por período, integridad referencial, importes y fechas válidas.

Antes de entregar la funcionalidad completa: API autenticada, doble confirmación,
correcciones y reversión, resumen por período, pago en mes distinto del período,
regresión de suscripciones y recorrido E2E. Validar también con PostgreSQL real;
la compilación SQL por sí sola no certifica el comportamiento de PostgreSQL.

## Estado de esta tanda

Se inicia con documentación y fundamentos de dominio/persistencia. La API y la UI
siguen pendientes. No aplicar la migración a la base personal ni desplegar en AWS
en esta tanda. No se ha iniciado ni detenido infraestructura AWS.

Resultado de verificación: **25 pruebas iniciales pasaron**; suite Python completa:
**161 pasaron y 3 se omitieron** (integración PostgreSQL sin URL de prueba configurada).
`git diff --check` sin problemas. Las migraciones se ejecutaron solamente sobre SQLite
temporal. No se verificó todavía contra PostgreSQL real ni se modificó la base personal.

Los cambios se encuentran sin commit en la rama existente `feature/T6-aws-console-lab`.
Antes de publicar este módulo, separarlo del trabajo del laboratorio AWS según el
flujo de ramas del proyecto.

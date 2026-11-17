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

API implementada: catálogo y registros bajo `/utilities`, con detalle, edición/archivo,
historial, confirmación/reversión y resumen mensual; autenticación OIDC existente.
El catálogo no tiene eliminación permanente en v1. Ya hay navegación y catálogo web
de consulta; los formularios de gestión siguen pendientes de S3.2.

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
- [x] **S2.1** Implementar repositorio y servicio: catálogo, archivo/reactivación e historial. Endpoints autenticados y 22 pruebas nuevas verificadas.
- [x] **S2.2** Implementar registro mensual, corrección, confirmación y reversión transaccionales. 29 pruebas nuevas, incluidas operaciones simultáneas sobre SQLite.
- [x] **S2.3** Exponer endpoints autenticados y resumen mensual; probar errores y concurrencia. Suite completa con PostgreSQL 18: 232 pruebas aprobadas, sin omisiones.
- [x] **S3.1** Añadir cliente API, tipos TypeScript y navegación «Servicios». Vista inicial de consulta conectada y verificada en escritorio/móvil.
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

### Avance S2.1: catálogo e historial de consulta

Implementados repositorio y servicio persistentes, y los siguientes endpoints con
la dependencia OIDC existente:

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| POST | `/utilities` | Crear con nombre y proveedor opcional; activo por defecto. |
| GET | `/utilities` | Listar todos; `?is_active=true` o `false` filtra por estado. |
| GET | `/utilities/{utility_id}` | Consultar el servicio, incluso archivado. |
| PATCH | `/utilities/{utility_id}` | Editar nombre/proveedor o archivar/reactivar con `is_active`. |
| GET | `/utilities/{utility_id}/entries` | Consultar períodos registrados, del más reciente al más antiguo. |

PATCH actualiza solo campos enviados: `provider: null` o vacío limpia el proveedor;
nombre vacío, `name: null`, `is_active: null`, estados no booleanos y objetos vacíos
se rechazan con 422. UUID inexistente devuelve 404; falta de autenticación, 401;
errores de almacenamiento, 500 con mensaje público sin detalles SQL.

Archivar/reactivar no modifica importes, fechas ni registros mensuales. El historial
incluye pendientes y pagados del servicio solicitado; un servicio sin registros
devuelve una lista vacía. No existe endpoint de eliminación permanente.

Verificación S2.1: **22 pruebas nuevas pasaron; suite completa: 183 pasaron y 3 se
omitieron** por falta de configuración de integración PostgreSQL. Bases temporales
SQLite; PostgreSQL real sigue pendiente. `git diff --check` sin problemas.

S2.2 es la siguiente tarea: creación/corrección de registros mensuales y confirmación/
reversión transaccional de pagos. El resumen mensual queda en S2.3. La interfaz sigue
pendiente y no se reconstruyeron contenedores ni se migró la base personal en S2.1.

### Avance S2.2: registros mensuales y pagos

Se añadieron estos endpoints autenticados:

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| POST | `/utilities/{utility_id}/entries` | Crear período pendiente o histórico pagado; responde 201. |
| PATCH | `/utilities/{utility_id}/entries/{entry_id}` | Corregir período, importe, vencimiento, notas y fecha de un pago existente. |
| POST | `/utilities/{utility_id}/entries/{entry_id}/confirm` | Confirmar pendiente; `{}` usa hoy en Lima y el importe actual. |
| POST | `/utilities/{utility_id}/entries/{entry_id}/undo` | Revertir pago, dejando pendiente con el mismo importe y período. |

Crear recibe `year`, `month`, `amount` y opcionalmente `due_date`, `paid_date`, `notes`.
Confirmar admite `amount` y `paid_date` opcionales. PATCH permite limpiar vencimiento
y notas con null, pero no año, mes, monto ni fecha de pago. Para cambiar pendiente a
pagado se usa confirmación; para volver a pendiente se usa reversión. La edición de
un pago ya confirmado permite corregir su fecha e importe. No hay borrado de períodos.

Reglas operativas: 409 para período duplicado, pago ya confirmado, reversión sin pago
o creación de un período en servicio archivado. Un servicio archivado permite corregir,
confirmar y revertir sus registros existentes. Reactivarlo permite crear más períodos.
Un registro ajeno al servicio o inexistente devuelve 404; entradas inválidas devuelven
422. Todos los endpoints exigen la autenticación existente.

Las escrituras mensuales son transaccionales: bloqueo del servicio con FOR UPDATE en
PostgreSQL y BEGIN IMMEDIATE antes de leer en SQLite. Los cambios de período verifican
duplicados antes de editar. Errores revierten la operación completa. La restricción
única del esquema conserva una segunda defensa para los períodos.

Verificación S2.2: **29 pruebas nuevas pasaron**, incluidas creación/confirmación/reversión
simultáneas (una operación aceptada y otra con conflicto), pagos entre meses, correcciones,
aislamiento entre servicios, archivo, autenticación, rollback y reapertura de conexiones.
La suite completa pasó con **212 pruebas y 3 omitidas** de integración PostgreSQL.
`git diff --check` sin problemas. PostgreSQL real sigue pendiente de S2.3/S4.

Siguiente tarea: **S2.3**, resumen mensual y verificación de integración con PostgreSQL.
No se reconstruyeron contenedores ni se migró la base personal en S2.2.

### Avance S2.3: resumen mensual e integración PostgreSQL

Implementado `GET /utilities/summary?year=2025&month=11`, autenticado. Año y mes son
obligatorios y usan los mismos límites que los registros (1900–9999 y 1–12). Se registra
la ruta estática antes de `/{utility_id}` para evitar que `summary` se valide como UUID.

Respuesta de ejemplo:

```json
{
  "year": 2025,
  "month": 11,
  "pending_count": 2,
  "paid_count": 1,
  "total_pending": "0.30",
  "total_paid": "50.35"
}
```

Los importes son PEN, con dos decimales; meses sin registros devuelven conteos 0 e
importes `"0.00"`. Una consulta agregada calcula conteos e importes en la misma lectura,
sumando céntimos para evitar errores de coma flotante. Incluye pendientes y pagos de
servicios archivados. No genera obligaciones para servicios sin registro mensual.

El resumen agrupa por el período del servicio, no por fecha de desembolso. Un pago de
noviembre realizado en diciembre cuenta en noviembre. En el futuro saldo financiero,
se consultará la fecha efectiva del pago en un reporte distinto.

Verificación S2.3: **12 pruebas nuevas de resumen** y **5 de integración de servicios
con PostgreSQL**. La suite completa se ejecutó con **PostgreSQL 18: 232 pruebas
aprobadas, ninguna omitida**. Pasaron también las tres integraciones previas de
suscripciones y migración SQLite→PostgreSQL. `git diff --check` sin problemas.

La integración verificó upgrade con suscripciones y renovaciones previas, Alembic sin
diferencias, downgrade/upgrade conservando datos anteriores, restricciones de BD,
rollback, autenticación con JWT RS256 firmado para pruebas y rechazo sin token/token
inválido, archivo/reactivación, correcciones y persistencia tras reconectar. Creación,
confirmación y reversión simultáneas tuvieron un éxito y un conflicto por operación.
Las claves de firma y JWKS fueron locales de prueba; no se contactó Keycloak real.

Se añadió `.venv/bin/python -m scripts.run_postgres_tests`: inicia un PostgreSQL
temporal con puerto aleatorio en loopback, almacenamiento en RAM y sin credenciales ni
volúmenes personales; ejecuta pytest y elimina el contenedor al terminar. Cada prueba
de integración crea y elimina su propio esquema. Puede recibir argumentos de pytest.

Siguiente tarea: **S3.1**, cliente API, tipos TypeScript y navegación «Servicios».
La app local sigue con su imagen anterior y la base personal sigue sin migrarse.

### Avance S3.1: integración del frontend y navegación

Se añadieron tipos TypeScript para catálogo, registros mensuales, correcciones,
confirmación de pago y resumen, respetando campos opcionales/null del backend y
conservando importes como cadenas decimales. El cliente API cubre todas las operaciones
de Servicios y reutiliza la autenticación, renovación de token y errores existentes.
El filtro `is_active=false` se envía correctamente y confirmar sin datos envía `{}`.

«Servicios» aparece en la barra lateral y en la navegación móvil de tres columnas.
La ruta `/servicios` abre una vista inicial de solo consulta del catálogo, con nombre,
proveedor y estado activo/archivado; maneja carga, catálogo vacío, error y reintento.
No muestra formularios ni acciones de gestión: corresponden a S3.2. Se mantiene el
sistema visual existente. La pestaña del navegador se llama «Control Budget».

FastAPI sirve `/servicios` al entrar directamente o recargar; los endpoints desconocidos
de `/utilities` conservan sus errores JSON. Vite reenvía `/utilities` a la API en desarrollo.

Verificación: **18 pruebas frontend aprobadas**, TypeScript y build correctos; regresión
Python **224 aprobadas, 8 omitidas** porque esta ejecución no configuró PostgreSQL
(su verificación completa de 232 pruebas quedó registrada en S2.3). Navegador Chromium
con base SQLite temporal y datos sintéticos: vista de escritorio 1440×960, móvil 390×844,
entrada directa, navegación a Suscripciones y regreso; sin desbordamiento horizontal en
móvil (ancho del documento = 390). Capturas locales en `output/playwright/`, excluidas de
Git. El detector visual solo señaló la fuente Inter preexistente; se preservó la identidad.

El servidor de revisión y el navegador se cerraron; la base temporal se eliminó. No se
actualizó Docker ni la base personal. Siguiente tarea: **S3.2**, vista mensual, detalle
y formularios para gestionar servicios y pagos.

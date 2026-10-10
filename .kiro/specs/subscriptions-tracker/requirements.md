# Requirements Document

## Introduction

Esta feature define los requisitos para una aplicación web de gestión de suscripciones de pago, construida con Python y FastAPI. El sistema permite a los usuarios crear, consultar, actualizar y eliminar suscripciones, calcular el gasto mensual total, y recibir alertas cuando una suscripción está próxima a renovarse automáticamente. El almacenamiento se mantiene en memoria durante la ejecución de la aplicación.

## Glossary

- **Subscription_Manager**: El componente principal de la aplicación que expone los endpoints HTTP para gestionar suscripciones.
- **Subscription**: Entidad que representa un servicio de pago recurrente con nombre, costo, ciclo de facturación, fecha de renovación y estado activo/inactivo.
- **Subscription_Store**: El almacén en memoria que persiste las suscripciones durante la ejecución de la aplicación.
- **Cost_Calculator**: El componente responsable de calcular el gasto mensual total a partir de las suscripciones activas.
- **Alert_Engine**: El componente responsable de evaluar las fechas de renovación y determinar qué suscripciones están dentro de la ventana de alerta.
- **subscription_id**: Identificador único asignado a cada suscripción en el momento de su creación.
- **billing_cycle**: Frecuencia de cobro de una suscripción. Valores permitidos: `monthly`, `yearly`.
- **renewal_date**: Fecha en formato ISO 8601 (`YYYY-MM-DD`) que indica la próxima fecha en que se realizará el cobro automático de la suscripción.
- **alert_window**: Período de anticipación previo a la `renewal_date` dentro del cual el sistema genera una alerta de vencimiento. El valor por defecto es 7 días para suscripciones `monthly` y 30 días para suscripciones `yearly`.
- **Renewal_Alert**: Objeto que representa una alerta de vencimiento próximo para una suscripción activa, incluyendo el `subscription_id`, `name`, `renewal_date`, `billing_cycle` y `days_until_renewal`.

---

## Requirements

### Requirement 1: Crear suscripción

**User Story:** Como usuario, quiero registrar una nueva suscripción de pago, para que pueda llevar un control de mis servicios contratados.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud POST a `/subscriptions` con `name`, `cost`, `billing_cycle`, `renewal_date` e `is_active`, THE Subscription_Manager SHALL crear la suscripción, almacenarla en el Subscription_Store y retornar HTTP 201 con la representación completa de la suscripción creada incluyendo su `subscription_id`.
2. WHEN el Subscription_Manager crea una suscripción, THE Subscription_Manager SHALL asignar un `subscription_id` único (UUID v4) que no colisione con ningún identificador existente en el Subscription_Store.
3. WHEN la solicitud de creación omite el campo `name`, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje que identifique `name` como el campo faltante requerido.
4. WHEN la solicitud de creación omite el campo `cost`, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje que identifique `cost` como el campo faltante requerido.
5. WHEN el campo `cost` contiene un valor menor o igual a 0, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que el costo debe ser un número positivo mayor a 0.
6. WHEN el campo `billing_cycle` contiene un valor distinto de `monthly` o `yearly`, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que los valores permitidos son `monthly` y `yearly`.
7. WHEN el campo `is_active` es omitido en la solicitud de creación, THE Subscription_Manager SHALL asignar el valor `true` como valor por defecto para `is_active`; IF el campo `is_active` es proporcionado explícitamente, THE Subscription_Manager SHALL usar el valor proporcionado sin sobrescribirlo con el valor por defecto.
8. WHEN la solicitud de creación omite el campo `renewal_date`, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje que identifique `renewal_date` como el campo faltante requerido.
9. WHEN el campo `renewal_date` contiene un valor que no es una fecha válida en formato ISO 8601 (`YYYY-MM-DD`), THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que el formato requerido es `YYYY-MM-DD`.
10. WHEN el campo `renewal_date` contiene una fecha anterior o igual a la fecha actual del servidor, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que la `renewal_date` debe ser una fecha futura.

---

### Requirement 2: Listar suscripciones

**User Story:** Como usuario, quiero ver todas mis suscripciones registradas, para que pueda conocer el estado actual de mis servicios.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud GET a `/subscriptions`, THE Subscription_Manager SHALL retornar HTTP 200 con la lista de todas las suscripciones almacenadas en el Subscription_Store.
2. IF el Subscription_Store no contiene suscripciones, THEN THE Subscription_Manager SHALL retornar HTTP 200 con una lista vacía (`[]`).
3. WHEN el Subscription_Manager retorna la lista de suscripciones, THE Subscription_Manager SHALL incluir en cada elemento exactamente los campos: `subscription_id`, `name`, `cost`, `billing_cycle`, `renewal_date` e `is_active`.
4. IF el Subscription_Store no está disponible durante la solicitud GET a `/subscriptions`, THEN THE Subscription_Manager SHALL retornar HTTP 500 con un mensaje indicando un error interno del servidor.

---

### Requirement 3: Actualizar suscripción

**User Story:** Como usuario, quiero modificar los datos de una suscripción existente, para que pueda mantener la información actualizada cuando cambien los términos del servicio.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud PUT a `/subscriptions/{subscription_id}` con uno o más campos válidos a actualizar (`name`, `cost`, `billing_cycle`, `renewal_date`, `is_active`), THE Subscription_Manager SHALL actualizar únicamente los campos proporcionados de la suscripción correspondiente en el Subscription_Store y retornar HTTP 200 con la representación completa de la suscripción actualizada.
2. IF el `subscription_id` proporcionado no existe en el Subscription_Store, THEN THE Subscription_Manager SHALL retornar HTTP 404 con un mensaje indicando que la suscripción no fue encontrada.
3. WHEN el campo `cost` está incluido en la solicitud de actualización y contiene un valor menor o igual a 0, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que el costo debe ser un número positivo mayor a 0; esta validación se aplica únicamente cuando `cost` es parte explícita del body de actualización.
4. WHEN el campo `billing_cycle` está incluido en la solicitud de actualización y contiene un valor distinto de `monthly` o `yearly`, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que los valores permitidos son `monthly` y `yearly`.
5. IF la solicitud PUT a `/subscriptions/{subscription_id}` no contiene ningún campo válido a actualizar, THEN THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que se debe proporcionar al menos un campo para actualizar.
6. WHEN el campo `renewal_date` está incluido en la solicitud de actualización y contiene un valor que no es una fecha válida en formato ISO 8601 (`YYYY-MM-DD`), THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que el formato requerido es `YYYY-MM-DD`.
7. WHEN el campo `renewal_date` está incluido en la solicitud de actualización y contiene una fecha anterior o igual a la fecha actual del servidor, THE Subscription_Manager SHALL retornar HTTP 422 con un mensaje indicando que la `renewal_date` debe ser una fecha futura.

---

### Requirement 4: Eliminar suscripción

**User Story:** Como usuario, quiero eliminar una suscripción que ya no utilizo, para que no aparezca en mi lista ni afecte mis cálculos de gasto.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud DELETE a `/subscriptions/{subscription_id}` y la suscripción existe en el Subscription_Store, THE Subscription_Manager SHALL eliminar permanentemente la suscripción del Subscription_Store y retornar HTTP 204 sin contenido en el cuerpo de la respuesta.
2. IF el `subscription_id` proporcionado no existe en el Subscription_Store, THEN THE Subscription_Manager SHALL retornar HTTP 404 con un mensaje indicando que la suscripción no fue encontrada.
3. WHEN una suscripción es eliminada del Subscription_Store, THE Subscription_Manager SHALL asegurar de forma atómica que la suscripción eliminada no aparece en respuestas posteriores a GET `/subscriptions` ni en el cálculo de GET `/subscriptions/summary`; la eliminación del store principal y la limpieza de referencias en el resumen SHALL ocurrir en una misma operación indivisible.

---

### Requirement 5: Calcular gasto mensual total

**User Story:** Como usuario, quiero obtener el total de mi gasto mensual en suscripciones activas, para que pueda evaluar cuánto estoy invirtiendo en servicios de pago.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud GET a `/subscriptions/summary`, THE Cost_Calculator SHALL calcular el gasto mensual total considerando únicamente las suscripciones con `is_active` igual a `true` y THE Subscription_Manager SHALL retornar HTTP 200 con el campo `total_monthly_cost` redondeado a 2 decimales.
2. WHEN el Cost_Calculator procesa una suscripción activa con `billing_cycle` igual a `yearly`, THE Cost_Calculator SHALL dividir su `cost` entre 12 para obtener el equivalente mensual antes de sumarlo al total.
3. IF no existen suscripciones con `is_active` igual a `true` en el Subscription_Store, THEN THE Cost_Calculator SHALL retornar un `total_monthly_cost` de `0.00`.
4. WHEN el Cost_Calculator procesa suscripciones activas con `billing_cycle` igual a `monthly`, THE Cost_Calculator SHALL sumar su `cost` directamente al total mensual sin normalización.
5. IF el Subscription_Store no está disponible durante la solicitud GET a `/subscriptions/summary`, THEN THE Subscription_Manager SHALL retornar HTTP 500 con un mensaje indicando un error interno del servidor.

---

### Requirement 6: Alertas de vencimiento de suscripción

**User Story:** Como usuario, quiero recibir alertas sobre mis suscripciones próximas a renovarse automáticamente, para que pueda decidir si cancelarlas antes de que se realice el cobro.

#### Acceptance Criteria

1. WHEN el usuario envía una solicitud GET a `/subscriptions/alerts`, THE Alert_Engine SHALL evaluar todas las suscripciones con `is_active` igual a `true` en el Subscription_Store y determinar cuáles tienen su `renewal_date` dentro de la `alert_window` correspondiente a partir de la fecha actual del servidor.
2. WHEN el Alert_Engine completa su evaluación, THE Subscription_Manager SHALL retornar HTTP 200 con la lista de Renewal_Alert de las suscripciones que cumplen la condición de alerta; la evaluación siempre se considera completada independientemente de si se encontraron suscripciones en la ventana de alerta o no.
3. WHEN el Alert_Engine evalúa una suscripción activa con `billing_cycle` igual a `monthly`, THE Alert_Engine SHALL aplicar una `alert_window` de 7 días; la suscripción se incluye en la lista si `days_until_renewal` es mayor o igual a 0 y menor o igual a 7.
4. WHEN el Alert_Engine evalúa una suscripción activa con `billing_cycle` igual a `yearly`, THE Alert_Engine SHALL aplicar una `alert_window` de 30 días; la suscripción se incluye en la lista si `days_until_renewal` es mayor o igual a 0 y menor o igual a 30.
5. WHEN el Alert_Engine genera una Renewal_Alert, THE Alert_Engine SHALL incluir los campos `subscription_id`, `name`, `renewal_date`, `billing_cycle` y `days_until_renewal`, donde `days_until_renewal` es la parte entera (floor) de la diferencia en días calendario entre la fecha actual del servidor y la `renewal_date`.
6. IF no existen suscripciones activas cuya `renewal_date` se encuentre dentro de la `alert_window` correspondiente, THEN THE Subscription_Manager SHALL retornar HTTP 200 con una lista vacía (`[]`).
7. WHEN el Alert_Engine evalúa suscripciones, THE Alert_Engine SHALL excluir del resultado todas las suscripciones con `is_active` igual a `false`, independientemente de su `renewal_date`.
8. WHEN el Subscription_Manager retorna la lista de Renewal_Alert, THE Subscription_Manager SHALL ordenar los resultados de forma ascendente por `days_until_renewal`, mostrando primero las suscripciones con vencimiento más próximo.
9. IF el Subscription_Store no está disponible durante la solicitud GET a `/subscriptions/alerts`, THEN THE Subscription_Manager SHALL retornar HTTP 500 con un mensaje indicando un error interno del servidor.

# Implementation Plan: Subscriptions Tracker

## Overview

Implementar una API REST con Python + FastAPI para gestionar suscripciones de pago recurrentes. La implementación sigue una arquitectura en capas (routers → services → store) con almacenamiento en memoria thread-safe. Se incluyen property-based tests con Hypothesis y tests unitarios con pytest para validar la lógica de negocio pura.

## Tasks

- [x] 1. Configurar estructura del proyecto y dependencias
  - Crear la estructura de directorios del proyecto: `app/`, `app/models/`, `app/routers/`, `app/services/`, `app/store/`, `tests/unit/`, `tests/property/`
  - Crear `requirements.txt` con las dependencias: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `pytest`, `hypothesis`, `pytest-cov`
  - Crear `app/__init__.py`, `app/models/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py`, `app/store/__init__.py`
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1_

- [x] 2. Implementar modelos de dominio y schemas Pydantic
  - [x] 2.1 Crear `app/models/subscription.py` con `BillingCycle`, `Subscription`, `SubscriptionCreate`, `SubscriptionUpdate`, `SummaryResponse`, `RenewalAlert` y `ErrorResponse`
    - Definir el enum `BillingCycle` con valores `monthly` y `yearly`
    - Implementar `Subscription` con campos: `subscription_id` (UUID), `name`, `cost` (Decimal), `billing_cycle`, `renewal_date` (date), `is_active` (bool, default True)
    - Implementar `SubscriptionCreate` con `field_validator` para `cost > 0` y `renewal_date` futura
    - Implementar `SubscriptionUpdate` con todos los campos opcionales y los mismos validadores
    - _Requirements: 1.2, 1.5, 1.6, 1.7, 1.9, 1.10, 3.3, 3.4, 3.6, 3.7_

  - [x] 2.2 Escribir property test: Property 3 — cost inválido es rechazado
    - **Property 3: Cualquier valor de cost menor o igual a cero es rechazado con HTTP 422**
    - **Validates: Requirements 1.5, 3.3**
    - Usar estrategia `invalid_cost` de Hypothesis en `tests/property/test_creation_properties.py`

  - [x] 2.3 Escribir property test: Property 4 — billing_cycle inválido es rechazado
    - **Property 4: Cualquier valor de billing_cycle distinto de los permitidos es rechazado con HTTP 422**
    - **Validates: Requirements 1.6, 3.4**
    - Usar estrategia `invalid_billing_cycle` en `tests/property/test_creation_properties.py`

  - [x] 2.4 Escribir property test: Property 5 — renewal_date inválida o no futura es rechazada
    - **Property 5: Cualquier renewal_date inválida o no futura es rechazada con HTTP 422**
    - **Validates: Requirements 1.9, 1.10, 3.6, 3.7**
    - Usar estrategia `past_or_today_date` en `tests/property/test_creation_properties.py`

- [x] 3. Implementar el SubscriptionStore
  - [x] 3.1 Crear `app/store/subscription_store.py` con la clase `SubscriptionStore`
    - Implementar `__init__` con `dict[str, Subscription]` y `threading.Lock`
    - Implementar métodos: `add`, `get`, `list_all`, `update`, `delete`, `is_available`
    - Todas las operaciones de escritura (`add`, `update`, `delete`) deben ejecutarse bajo `threading.Lock`
    - `is_available` retorna `False` si el dict interno no está inicializado
    - _Requirements: 2.1, 2.4, 4.1, 4.3, 5.5, 6.9_

  - [x] 3.2 Escribir tests unitarios para SubscriptionStore
    - Crear `tests/unit/test_subscription_store.py`
    - Cubrir: add y recuperación, get con ID inexistente (None), list_all vacío, update parcial, delete exitoso, delete con ID inexistente (False), is_available
    - _Requirements: 2.2, 4.1, 4.2, 4.3_

- [x] 4. Implementar CostCalculator y AlertEngine
  - [x] 4.1 Crear `app/services/cost_calculator.py` con la clase `CostCalculator`
    - Implementar `monthly_cost(subscription)`: retorna `cost` si monthly, `round(cost / 12, 2)` si yearly
    - Implementar `total_monthly_cost(subscriptions)`: suma solo activas, redondea a 2 decimales
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.2 Crear `app/services/alert_engine.py` con `ALERT_WINDOW` y la clase `AlertEngine`
    - Definir `ALERT_WINDOW = {BillingCycle.monthly: 7, BillingCycle.yearly: 30}`
    - Implementar `days_until_renewal(renewal_date, today)`: floor de diferencia en días calendario
    - Implementar `evaluate(subscriptions, today)`: filtra activas, aplica ventana, retorna lista ordenada por `days_until_renewal` ascendente
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.7, 6.8_

  - [x] 4.3 Escribir tests unitarios para CostCalculator
    - Crear `tests/unit/test_cost_calculator.py`
    - Cubrir: costo mensual de suscripción monthly, costo mensual de suscripción yearly, total con mezcla, total solo inactivas → 0.00
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.4 Escribir tests unitarios para AlertEngine
    - Crear `tests/unit/test_alert_engine.py`
    - Cubrir: suscripción dentro de ventana monthly (0 días), suscripción fuera de ventana, suscripción inactiva excluida, lista vacía, orden ascendente
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.7, 6.8_

  - [x] 4.5 Escribir property test: Property 9 — cálculo de gasto mensual total
    - **Property 9: El cálculo de gasto mensual total es correcto para cualquier mezcla de suscripciones**
    - **Validates: Requirements 5.1, 5.2, 5.4**
    - Crear `tests/property/test_summary_properties.py`

  - [x] 4.6 Escribir property test: Property 10 — alertas contienen exactamente las suscripciones correctas
    - **Property 10: Las alertas retornadas contienen exactamente las suscripciones activas dentro de la ventana correspondiente**
    - **Validates: Requirements 6.1, 6.3, 6.4, 6.7**
    - Crear `tests/property/test_alerts_properties.py`

  - [x] 4.7 Escribir property test: Property 11 — days_until_renewal es el floor exacto de días calendario
    - **Property 11: El campo days_until_renewal en cada alerta es el floor exacto de días calendario**
    - **Validates: Requirements 6.5**
    - Agregar a `tests/property/test_alerts_properties.py`

  - [x] 4.8 Escribir property test: Property 12 — alertas ordenadas ascendentemente por days_until_renewal
    - **Property 12: La lista de alertas está ordenada ascendentemente por days_until_renewal**
    - **Validates: Requirements 6.8**
    - Agregar a `tests/property/test_alerts_properties.py`

- [x] 5. Checkpoint — Verificar lógica de negocio pura
  - Asegurarse de que todos los tests de store, CostCalculator y AlertEngine pasan correctamente. Preguntar al usuario si hay dudas antes de continuar.

- [x] 6. Implementar SubscriptionService
  - [x] 6.1 Crear `app/services/subscription_service.py` con la clase `SubscriptionService`
    - Constructor recibe `store: SubscriptionStore`
    - Implementar `create(data: SubscriptionCreate) -> Subscription`: genera UUID v4, instancia `Subscription`, llama `store.add`, verifica disponibilidad del store
    - Implementar `list_all() -> list[Subscription]`: verifica disponibilidad, llama `store.list_all`
    - Implementar `update(subscription_id, data: SubscriptionUpdate) -> Subscription`: verifica disponibilidad, verifica que al menos un campo no es None, llama `store.update`, lanza 404 si no existe
    - Implementar `delete(subscription_id) -> None`: verifica disponibilidad, llama `store.delete`, lanza 404 si no existe
    - Implementar `get_summary() -> SummaryResponse`: verifica disponibilidad, llama `CostCalculator.total_monthly_cost`
    - Implementar `get_alerts() -> list[RenewalAlert]`: verifica disponibilidad, llama `AlertEngine.evaluate` con `date.today()`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2, 3.5, 4.1, 4.2, 5.1, 5.5, 6.1, 6.2, 6.9_

  - [x] 6.2 Escribir property test: Property 1 — subscription_id son UUIDs v4 válidos y únicos
    - **Property 1: Los subscription_id asignados son UUIDs v4 válidos y únicos**
    - **Validates: Requirements 1.2**
    - Agregar a `tests/property/test_creation_properties.py`

  - [x] 6.3 Escribir property test: Property 2 — is_active no es sobrescrito por el valor por defecto
    - **Property 2: El campo is_active nunca es sobrescrito por el valor por defecto**
    - **Validates: Requirements 1.7**
    - Agregar a `tests/property/test_creation_properties.py`

- [x] 7. Implementar FastAPI routers
  - [x] 7.1 Crear `app/routers/subscriptions.py` con todos los endpoints de suscripciones
    - Registrar rutas en el orden correcto: `/subscriptions/summary` y `/subscriptions/alerts` ANTES de `/subscriptions/{subscription_id}`
    - `POST /subscriptions` → 201 con `Subscription`, delegar a `service.create`
    - `GET /subscriptions` → 200 con `list[Subscription]`, delegar a `service.list_all`
    - `PUT /subscriptions/{subscription_id}` → 200 con `Subscription`, delegar a `service.update`
    - `DELETE /subscriptions/{subscription_id}` → 204 sin cuerpo, delegar a `service.delete`
    - `GET /subscriptions/summary` → 200 con `SummaryResponse`, delegar a `service.get_summary`
    - `GET /subscriptions/alerts` → 200 con `list[RenewalAlert]`, delegar a `service.get_alerts`
    - Mapear `HTTPException` 404 y 500 a `ErrorResponse`
    - _Requirements: 1.1, 2.1, 2.4, 3.1, 3.2, 3.5, 4.1, 4.2, 5.1, 5.5, 6.2, 6.9_

  - [x] 7.2 Crear `app/main.py` con la aplicación FastAPI principal
    - Instanciar `SubscriptionStore`, `SubscriptionService`, incluir el router
    - Exponer la instancia `app` de FastAPI
    - _Requirements: 1.1, 2.1, 4.1, 5.1, 6.1_

  - [x] 7.3 Escribir tests unitarios para endpoints — edge cases
    - Crear `tests/unit/test_routes_edge_cases.py` usando `TestClient` de FastAPI + `httpx`
    - Cubrir: POST sin `name` → 422, POST sin `cost` → 422, POST sin `renewal_date` → 422, GET vacío → `[]`, DELETE ID inexistente → 404, PUT ID inexistente → 404, PUT body vacío → 422, GET alerts sin suscripciones en ventana → `[]`, store no disponible → 500
    - _Requirements: 1.3, 1.4, 1.8, 2.2, 3.2, 3.5, 4.2, 6.6_

- [x] 8. Implementar property tests de endpoints
  - [x]* 8.1 Escribir property test: Property 6 — cada suscripción en la lista contiene exactamente los campos requeridos
    - **Property 6: Cada suscripción en la lista contiene exactamente los campos requeridos**
    - **Validates: Requirements 2.3**
    - Crear `tests/property/test_list_properties.py`

  - [x]* 8.2 Escribir property test: Property 7 — PUT actualiza únicamente los campos provistos y preserva el resto
    - **Property 7: PUT actualiza únicamente los campos provistos y preserva el resto**
    - **Validates: Requirements 3.1**
    - Crear `tests/property/test_update_properties.py`

  - [x]* 8.3 Escribir property test: Property 8 — suscripción eliminada no aparece en endpoints posteriores
    - **Property 8: Una suscripción eliminada no vuelve a aparecer en ningún endpoint posterior**
    - **Validates: Requirements 4.1, 4.3**
    - Crear `tests/property/test_delete_properties.py`

- [x] 9. Checkpoint final — Asegurarse de que todos los tests pasan
  - Ejecutar `pytest tests/ --cov=app` y verificar que todos los tests pasan sin errores. Preguntar al usuario si hay dudas o ajustes antes de dar por concluida la implementación.

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia los requisitos específicos para trazabilidad
- Los checkpoints aseguran validación incremental antes de avanzar
- Los property tests usan Hypothesis con `max_examples=100`
- Los unit tests usan pytest con `TestClient` de FastAPI y `httpx`
- El orden de registro de rutas en el router es crítico: `/summary` y `/alerts` deben preceder a `/{subscription_id}`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1"] },
    { "id": 1, "tasks": ["3.1", "4.1", "4.2"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.2", "4.3", "4.4"] },
    { "id": 3, "tasks": ["4.5", "4.6", "4.7", "4.8", "6.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 5, "tasks": ["7.2"] },
    { "id": 6, "tasks": ["7.3", "8.1", "8.2", "8.3"] }
  ]
}
```

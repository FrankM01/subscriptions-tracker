# Gastos diarios: API y verificación G2

Implementada en `feature/daily-expenses-module`. Todas las rutas usan la
autenticación OIDC existente. No requiere otra migración después de G1.

## Registro de un gasto

`POST /expenses` devuelve 201 y el gasto persistido:

```json
{
  "description": "Bebidas",
  "quantity": "2",
  "total_amount": "6.00",
  "expense_date": "2026-11-17",
  "category_id": "UUID de Alimentación",
  "subcategory_id": "UUID de Bebidas",
  "notes": null
}
```

Los UUID se obtienen del catálogo; los textos del ejemplo son marcadores.
El total sigue siendo S/ 6.00. Cantidad por defecto 1, fecha por defecto hoy
en Lima; subcategoría y notas opcionales. La respuesta incluye `expense_id`
e `is_voided`. Los decimales son cadenas, con cantidad en tres decimales y
total en dos al recuperar de la base.

## Endpoints

| Método y ruta | Uso |
| --- | --- |
| `GET /expense-categories` | Catálogo completo, incluidas archivadas, con subcategorías anidadas. |
| `POST /expense-categories` | Crear categoría con `{name}`. |
| `PATCH /expense-categories/{id}` | Renombrar o archivar/reactivar con `{name, is_active}` parciales. |
| `POST /expense-categories/{id}/subcategories` | Crear subcategoría con `{name}` dentro del padre. |
| `PATCH /expense-categories/{id}/subcategories/{sid}` | Renombrar o archivar/reactivar; no admite cambiar padre. |
| `POST /expenses` | Crear gasto realizado. |
| `GET /expenses?year=2026&month=11` | Consultar el mes con filtros y paginación. |
| `GET /expenses/{id}` | Consultar un gasto, incluso anulado. |
| `PATCH /expenses/{id}` | Editar los campos del gasto vigente. |
| `POST /expenses/{id}/void` | Anular sin borrar. |
| `POST /expenses/{id}/restore` | Restaurar conservando clasificación, fecha e importe. |
| `GET /expenses/summary?year=2026&month=11` | Totales y agrupaciones de gastos vigentes por fecha real. |

No hay endpoints de borrado. Todas las operaciones de edición usan PATCH
parcial: se requiere al menos un campo, no se admiten campos desconocidos y
solo notas y subcategoría se pueden limpiar con null. No se puede modificar
`is_voided` desde PATCH; se usan los comandos de anulación/restauración.

## Clasificación y estados

Los nombres se normalizan eliminando espacios redundantes y se comparan sin
distinguir mayúsculas dentro del mismo padre/nivel. Los nombres archivados
siguen reservados; se pueden reactivar en lugar de duplicarlos.

Una nueva asignación requiere categoría activa y subcategoría activa del
padre correcto. Archivar un padre no cambia los indicadores propios de sus
hijos, pero los deja indisponibles para asignar. El consumidor debe considerar
ambos estados. Para reactivar un hijo se debe reactivar primero su padre.

Editar importe, cantidad, fecha, descripción o notas de un gasto histórico no
obliga a cambiar una clasificación archivada. Cambiar de categoría limpia
automáticamente la subcategoría si no se incluye una nueva; una pareja explícita
incompatible se rechaza. La API no permite mover subcategorías de padre.

Un gasto anulado queda fuera de los análisis, pero disponible para consulta y
restauración. Se debe restaurar antes de editarlo. Restaurar mantiene categorías
archivadas sin convertir esa operación en una asignación nueva. Una segunda
anulación o restauración del mismo estado devuelve 409.

## Filtros y resúmenes

Listado y resumen requieren `year` (1900–9999) y `month` (1–12). Comparten
filtros opcionales `category_id`, `subcategory_id` y `search` por descripción.
Los caracteres `%` y `_` de búsqueda son texto literal, no comodines SQL.

El listado acepta `state=active|voided|all` (active por defecto), `limit`
(50 por defecto, 1–200) y `offset` (desde cero). Devuelve `items`, `total_count`,
`limit` y `offset`, con fecha descendente y UUID para desempatar. Conteo y
página se obtienen de la misma consulta; una página vacía conserva el conteo.

El resumen siempre excluye anulados, conserva los demás filtros y no se
limita a la página visible. Devuelve:

- `count`, `total_amount`, `year` y `month`.
- `categories`: identificador/nombre, cantidad de registros y total por categoría.
- `subcategories`: lo anterior con padre y subcategoría; null representa
  «Sin subcategoría» dentro de ese padre.
- `days`: fecha, conteo, total diario y acumulado.

Las agrupaciones incluyen categorías archivadas y usan sus nombres actuales.
Los días sin registros se completan con ceros: todos los días de un mes pasado,
hasta hoy en el mes actual y ninguno en meses futuros. No hay proyecciones.
Los importes se calculan con enteros/Decimal; nunca se multiplican por cantidad.
Una sola consulta lee gastos y etiquetas para mantener coherencia entre los
totales, sus agrupaciones y la serie diaria.

## Transacciones, errores y validación

Cada escritura es transaccional. PostgreSQL bloquea el gasto con `FOR UPDATE`
al editar/anular/restaurar. Crear/asignar clasificación y editar su catálogo
bloquea el mismo padre, serializando archivo y asignaciones nuevas. SQLite
usa `BEGIN IMMEDIATE` antes de leer. La restricción única resuelve carreras
de nombres duplicados, traducidas a 409.

404 indica un recurso inexistente; 409 un estado incompatible o nombre duplicado;
422 entrada inválida o subcategoría de otro padre. Las fallas de almacenamiento
devuelven 500 con mensaje público, sin SQL ni credenciales.

**364 pruebas Python aprobadas con PostgreSQL 18 temporal y SQLite**, ninguna
omitida. Se añadieron 38 casos API: 19 ejecutados con cada motor. Cubren:

- Cantidad independiente del total, persistencia y ciclo editar/anular/restaurar.
- Catálogo, nombres duplicados, padres incorrectos, archivo y nuevas asignaciones.
- Ejemplo S/ 17, filtros reconciliados, páginas vacías, agrupaciones y acumulados.
- Meses vacíos, bisiestos, actuales y futuros; edición que cambia el mes del gasto.
- Entrada inválida sin cambios parciales y errores públicos de almacenamiento.
- Anulación/restauración simultáneas, archivo contra creación y nombres concurrentes.
- Protección de todas las rutas y ciclo con JWT firmado de prueba contra PostgreSQL.

La base personal y los contenedores de la app no se modificaron. El frontend
corresponde a G3–G4; esta etapa no tiene interfaz nueva ni requiere build frontend.

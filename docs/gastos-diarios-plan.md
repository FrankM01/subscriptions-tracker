# Gastos diarios: alcance y tareas

Plan aprobado el 17 de noviembre de 2026. Rama `feature/daily-expenses-module`.

## Decisiones acordadas

Cada registro es un gasto realizado: descripción/producto, cantidad positiva
con hasta tres decimales (inicialmente 1), importe **total** positivo en PEN
con hasta dos decimales, fecha real (hoy en Lima por defecto), categoría
obligatoria, subcategoría opcional y notas opcionales.

Cantidad 2 e importe S/ 6 suman S/ 6, nunca S/ 12. Se admiten fechas anteriores
desde 1900, no futuras. Importe máximo S/ 9,999,999.99; cantidad máxima
999,999.999. Las cantidades no generan precios unitarios ni modifican el total.

El formulario registra un gasto a la vez. «Guardar y agregar otro» conserva
la fecha y limpia los demás campos. Los gastos se pueden editar, anular y
restaurar. La anulación requiere confirmación, es recuperable y excluye el
registro de totales y gráficos; no hay borrado definitivo en esta versión.

Categorías y subcategorías admiten creación, renombrado, archivo y reactivación.
Archivar conserva el historial y sus importes, pero impide nuevas asignaciones;
si se archiva una categoría, sus subcategorías tampoco se podrán asignar.
Una subcategoría utilizada no cambia de padre. Las restauraciones conservan
la clasificación original, aunque esté archivada. Nombres únicos sin distinguir
mayúsculas dentro del mismo nivel/padre, normalizando espacios.

Se inicializan Alimentación, Transporte, Compras, Salud, Entretenimiento y
Otros; Alimentación incluye Desayuno, Almuerzo, Cena y Bebidas; Transporte,
Pasajes; Salud, Medicinas. El usuario puede administrar este catálogo.

## Interfaz y análisis

«Gastos diarios» tendrá vistas Movimientos y Análisis que comparten mes,
búsqueda de descripción y filtros de categoría/subcategoría. Movimientos se
agrupa por día y tiene filtro para anulados. Los análisis siempre excluyen
anulados y muestran total y número de gastos vigentes según los demás filtros.

Gráficos SVG adaptables con tabla accesible: barras por categoría, desglose por
subcategoría (incluido «Sin subcategoría») y evolución con selector Diario /
Acumulado. Días transcurridos sin gastos: cero; meses anteriores: todos sus
días; no hay proyecciones futuras. El dashboard tendrá un bloque separado
con total del mes y enlace al módulo.

No se integran automáticamente pagos de otros módulos, ni se calcula saldo
bancario. Fuera de alcance: ingresos, devoluciones, presupuestos por categoría,
comprobantes/importación, pendientes y Sankey.

## Etapas

- [x] G0: alcance, documentación y rama independiente.
- [x] G1: contratos, persistencia, catálogo inicial y migración aditiva.
- [x] G2: repositorio, servicio y API autenticada `/expenses` y `/expense-categories`.
- [x] G3: registro rápido, historial, edición, anulación/restauración y categorías.
- [ ] G4: análisis mensual, gráficos y resumen del dashboard.
- [ ] G5: verificación integral con PostgreSQL temporal, frontend y navegador.
- [ ] G6: respaldo restaurado y actualización del entorno personal.

G2 debe validar categoría activa y pertenencia/actividad de subcategoría al
asignar clasificación. Editar otros campos de un gasto con clasificación
archivada debe conservarla. Cambiar categoría debe limpiar o reemplazar la
subcategoría anterior. Anular/restaurar serán operaciones atómicas y no
borrarán gastos. No se impide registrar dos gastos legítimos iguales.

Resumen mensual calculado por fecha real del gasto, con agregados en backend
para totales, categorías/subcategorías y series diarias. Cliente autenticado,
estados de carga/error/vacío y bloqueo de doble envío en los formularios.

## Persistencia y aceptación

Tres tablas: categorías, subcategorías y gastos. El total se guarda en centavos;
la cantidad se guarda en milésimas enteras para preservar exactamente tres
decimales también en SQLite. La FK compuesta garantiza que la subcategoría
pertenezca a la categoría del gasto, además de las FK de los padres.

Verificar S/ 8 de almuerzo + S/ 3 desayuno + S/ 3 movilidad + S/ 3 bebidas =
S/ 17. Cantidad 2 y total S/ 6 deben seguir sumando S/ 6. Cubrir fracciones,
clasificación inválida, edición de agregados, archivo sin pérdida histórica,
anulación/restauración, filtros y meses vacíos. Migración y reversión deben
conservar los datos de Suscripciones, Servicios y Deudas.

G0–G1 trabajan solo con código y bases temporales; no migran ni reconstruyen
la app personal. La actualización local queda exclusivamente para G6.

## Verificación G1

**326 pruebas Python aprobadas con PostgreSQL 18 temporal**, ninguna omitida.
Se añadieron 34 casos: 14 de contratos y 10 de persistencia/migración ejecutados
en cada motor (SQLite y PostgreSQL). Cubren importes independientes de cantidad,
fracciones exactas, validaciones, catálogo inicial, pertenencia de subcategoría,
FK y restricciones, archivo sin pérdida de gastos, y reversión conservando
Servicios y Deudas. La regresión previa verifica también Suscripciones.

Alembic `check` confirma correspondencia entre modelos y migración; el catálogo
recupera los mismos identificadores al revertir y volver a migrar. `git diff
--check` sin errores. Sin cambios frontend en esta etapa, sin commit automático
y sin aplicar migraciones en la base personal. La API y la validación de
actividad de categorías se completaron en [G2](gastos-diarios-api.md).

La interfaz de registro e historial se completó en [G3](gastos-diarios-interfaz.md).
La siguiente etapa es G4: análisis mensual, gráficos y resumen del dashboard.

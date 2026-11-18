# Gastos diarios: interfaz G3

G3 implementa `/gastos` y `/gastos/categorias`, integrados en la navegación
principal y en el cliente autenticado existente. Las rutas directas sirven la
aplicación; una ruta API desconocida conserva su respuesta JSON 404.

## Registrar y corregir

El formulario recoge producto o descripción, cantidad (1 por defecto, hasta
tres decimales), importe total, fecha, categoría obligatoria, subcategoría y
notas opcionales. La cantidad no multiplica el importe: dos bebidas con total
S/ 6 registran S/ 6. La fecha comienza en el día actual de Lima y admite fechas
pasadas, desde 1900, sin fechas futuras.

**Guardar y agregar otro** conserva solo la fecha y devuelve el foco a la
descripción; los demás datos se limpian y la cantidad vuelve a 1. Guardar
normalmente cierra el editor. Ambos caminos muestran el mes del gasto guardado.
Los errores mantienen el formulario y sus datos; se bloquea el doble envío.

Editar permite conservar la clasificación original archivada para corregir
otros datos. No permite asignar una clasificación archivada nueva. Cambiar la
categoría limpia la subcategoría anterior.

## Movimientos y categorías

El historial se agrupa por fecha y pagina de 50 en 50. Mes, categoría,
subcategoría, búsqueda y estado se conservan en la URL. No presenta sumas
parciales de un día como si fueran totales. El estado predeterminado muestra
vigentes; también pueden consultarse anulados o todos.

Anular y restaurar requieren confirmación explícita y conservan el registro.
Los anulados deben restaurarse antes de editar. El catálogo permite crear,
renombrar, archivar y reactivar categorías y subcategorías, conservando sus
gastos históricos. Una subcategoría no se mueve a otro padre y queda
indisponible para nuevas asignaciones cuando su categoría está archivada.

La interfaz conserva el sistema visual existente, incorpora cinco destinos
en la navegación móvil y ofrece estados de carga, error, reintento y vacío.
La carga del catálogo y la del historial manejan errores independientemente.

## Verificación

- 56 pruebas frontend aprobadas, incluidas 11 nuevas de gastos y categorías.
- 364 pruebas Python aprobadas con PostgreSQL 18 temporal, ninguna omitida.
- TypeScript y build Vite aprobados; 2 recorridos E2E existentes aprobados.
- Navegador con FastAPI y PostgreSQL temporal: registro consecutivo, conservación
  exclusiva de fecha, recarga persistente y total S/ 14 para cantidad 2/total
  S/ 6 más cantidad 0.125/total S/ 8; anulación y restauración del gasto de S/ 6.
- Inspección de escritorio 1440 px y móvil 390 px; sin desbordamiento horizontal
  a 390 y 320 px. Capturas locales en `output/playwright/expenses-g3-*.png`.
- Revisión independiente de interfaz: disposición **ship**, sin hallazgos
  materiales en el alcance revisado. Detector de diseño sin hallazgos.

El navegador usa autenticación de prueba en el entorno aislado; no sustituye
la comprobación con la sesión real de Keycloak prevista en G6.

No se aplicaron migraciones ni se actualizaron los contenedores personales.
No se realizó commit automático. G4 añadirá Análisis, gráficos y el resumen
del dashboard; G5 verificará el módulo completo y G6 actualizará el entorno
personal después de respaldar y verificar la restauración.

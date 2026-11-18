# Gastos diarios: análisis mensual G4

En `/gastos`, las vistas **Movimientos** y **Análisis** comparten mes, búsqueda
de descripción, categoría y subcategoría en la URL. El cambio de vista conserva
estos filtros; limpiar filtros conserva el mes y la vista. El estado de
Movimientos (vigentes/anulados/todos) se oculta en Análisis y no se envía al
resumen: los análisis siempre excluyen anulados. Tampoco se envía paginación.

## Gráficos y tablas

La vista consume `/expenses/summary` mediante el cliente autenticado existente.
Total, número de gastos, agrupaciones y acumulados vienen del backend; el
frontend no suma importes ni multiplica la cantidad. Solo convierte importes
a número para escalar la geometría de los SVG; las etiquetas y tablas conservan
los importes entregados por la API.

- Barras por categoría, con nombre e importe explícito.
- Barras por categoría/subcategoría, incluyendo «Sin subcategoría» dentro de
  cada categoría para evitar agrupar padres distintos bajo una misma etiqueta.
- Evolución con selector **Diario / Acumulado**. Usa los días del resumen:
  meses anteriores completos, mes actual hasta hoy en Lima, sin días futuros.
  Un día sin gastos tiene importe diario cero y conserva el acumulado anterior.
- Cada gráfico dispone de tabla desplegable con encabezados y leyenda. La
  tabla de evolución incluye fecha, número de gastos, importe diario y acumulado.
  Los desplegables nativos funcionan con teclado.

Los meses sin gastos vigentes muestran total cero y un estado vacío, sin
dibujar series ficticias. Carga, errores y reintentos no muestran totales
anteriores como si correspondieran a los filtros actuales. Las respuestas
obsoletas se ignoran al cambiar filtros o desmontar la vista.

## Resumen del dashboard

**Gastos diarios de este mes** muestra total y número de gastos vigentes del mes
actual de Lima. El enlace abre directamente Análisis en ese período. Su carga
y reintento son independientes de Suscripciones, Servicios y Deudas.

El bloque explica que incluye únicamente registros de Gastos diarios. No suma
estimaciones de suscripciones, pagos de servicios o cuotas, ni pretende
representar el saldo bancario.

## Verificación G4

- 63 pruebas frontend aprobadas (7 nuevas respecto de G3): totales y tablas,
  categorías sin subcategoría, días cero, selector, filtros compartidos,
  carga/error/reintento, meses vacíos/futuros, respuestas obsoletas, resumen del
  dashboard y petición autenticada sin estado ni paginación.
- TypeScript y build Vite aprobados; 2 E2E existentes aprobados usando el
  Chromium de pruebas instalado en `/tmp/control-budget-playwright-browsers`.
- 364 pruebas Python aprobadas con PostgreSQL 18 temporal, ninguna omitida.
  Incluyen reconciliación de totales, clasificación, anulación/restauración,
  días cero, meses actuales, anteriores, bisiestos y futuros.
- Navegador con FastAPI/PostgreSQL temporal: S/ 8 almuerzo + S/ 3 desayuno +
  S/ 3 movilidad + S/ 3 bebidas = S/ 17; bebidas con cantidad 2 siguen sumando
  S/ 3. Filtro Bebidas = S/ 3; cambio entre vistas conserva clasificación.
  Anular bebidas reduce el total a S/ 14; restaurar recupera S/ 17. Se comprobó
  error HTTP 500 simulado y reintento, apertura de tabla con Enter y total de
  S/ 17 en el dashboard.
- Capturas de escritorio 1440 px y móvil 390 px en
  `output/playwright/expenses-g4-*.png`; comprobación de desbordamiento también
  a 320 px. Detector de diseño sin hallazgos.
- Revisión independiente: disposición **ship**, sin hallazgos materiales
  pendientes; confirmó el texto de acumulados y la legibilidad de la tabla móvil.

No se modificaron la base ni los contenedores personales. La autenticación de
navegador usa el modo de pruebas del entorno aislado; la sesión real de
Keycloak se comprobará durante G6. No se realizó commit automático.

G5 realizará la verificación integral del módulo; G6 preparará y verificará
los respaldos antes de actualizar la app personal.

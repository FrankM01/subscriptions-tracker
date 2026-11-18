import { Link } from "react-router-dom";
import { useExpenseSummary } from "../expenses";
import { formatMoney, todayInLima } from "../format";
import { formatUtilityPeriod, parseUtilityPeriod } from "../utilities";
import { ErrorState, LoadingState } from "./Feedback";

export function ExpenseDashboardSummary() {
  const period = todayInLima().slice(0, 7);
  const { summary, loading, error, reload } = useExpenseSummary(parseUtilityPeriod(period)!);
  return <section className="utility-dashboard" aria-labelledby="expense-dashboard-title">
    <div className="utility-dashboard-heading"><div><h2 id="expense-dashboard-title">Gastos diarios de este mes</h2><p>{formatUtilityPeriod(period)}</p></div><Link className="text-link" to={`/gastos?period=${period}&view=analysis`}>Ver análisis de gastos</Link></div>
    {loading ? <LoadingState label="Cargando resumen de gastos diarios…" /> : error ? <ErrorState message={error} onRetry={reload} /> : summary && <>
      <dl className="utility-totals" aria-label="Totales de gastos diarios del mes"><div><dt>Gastos vigentes · {summary.count}</dt><dd>{formatMoney(summary.total_amount)}</dd></div></dl>
      {summary.count === 0 && <p className="utility-help">Aún no hay gastos diarios vigentes registrados este mes.</p>}
      <p className="utility-help">Por fecha real del gasto, sin anulados. Este total solo incluye registros de Gastos diarios; no incorpora pagos de los otros módulos.</p>
    </>}
  </section>;
}

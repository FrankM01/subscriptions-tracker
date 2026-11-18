import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { formatMoney, todayInLima } from "../format";
import type { DebtMonthlySummary } from "../types";
import { formatUtilityPeriod, parseUtilityPeriod } from "../utilities";
import { ErrorState, LoadingState } from "./Feedback";

export function DebtDashboardSummary() {
  const period = todayInLima().slice(0, 7);
  const [summary, setSummary] = useState<DebtMonthlySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const { year, month } = parseUtilityPeriod(period)!;
    api.getDebtMonthlySummary(year, month).then((value) => {
      if (active) setSummary(value);
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof ApiError ? caught.message : "No se pudo cargar el resumen de deudas.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, revision]);

  return <section className="utility-dashboard" aria-labelledby="debt-dashboard-title">
    <div className="utility-dashboard-heading">
      <div><h2 id="debt-dashboard-title">Deudas de este mes</h2><p>{formatUtilityPeriod(period)}</p></div>
      <Link className="text-link" to={`/deudas?period=${period}`}>Ver cuotas del mes</Link>
    </div>
    {loading ? <LoadingState label="Cargando resumen de deudas…" /> : error ? <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} /> : summary && <>
      <dl className="utility-totals" aria-label="Totales de deudas del mes">
        <div><dt>Cuotas pendientes · {summary.pending_count}</dt><dd>{formatMoney(summary.total_pending)}</dd></div>
        <div><dt>Cuotas pagadas · {summary.paid_count}</dt><dd>{formatMoney(summary.total_paid)}</dd></div>
      </dl>
      {summary.pending_count + summary.paid_count === 0 && <p className="utility-help">No hay cuotas con vencimiento este mes.</p>}
      <div className="utility-notice">
        <h3>Atrasos de meses anteriores</h3>
        {summary.overdue_before_month_count > 0 ? <p>{summary.overdue_before_month_count} {summary.overdue_before_month_count === 1 ? "cuota vencida pendiente" : "cuotas vencidas pendientes"} · <strong>{formatMoney(summary.total_overdue_before_month)}</strong></p> : <p>No tienes cuotas pendientes vencidas de meses anteriores.</p>}
        <Link className="text-link" to="/deudas">Ver todas las deudas</Link>
      </div>
      <p className="utility-help">Importes por mes de vencimiento, incluidas deudas archivadas. La fecha real de pago puede pertenecer a otro mes. Las cuotas previas declaradas no se cuentan como pagos registrados.</p>
    </>}
  </section>;
}

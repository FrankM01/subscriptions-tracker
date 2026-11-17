import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { formatMoney, todayInLima } from "../format";
import type { UtilityMonthlySummary } from "../types";
import { formatUtilityPeriod, parseUtilityPeriod } from "../utilities";
import { ErrorState, LoadingState } from "./Feedback";

export function UtilityDashboardSummary() {
  const period = todayInLima().slice(0, 7);
  const [summary, setSummary] = useState<UtilityMonthlySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const { year, month } = parseUtilityPeriod(period)!;
    api.getUtilityMonthlySummary(year, month).then((result) => {
      if (active) setSummary(result);
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof ApiError ? caught.message : "No se pudo cargar el resumen de servicios.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, revision]);

  return <section className="utility-dashboard" aria-labelledby="utility-dashboard-title">
    <div className="utility-dashboard-heading">
      <div><h2 id="utility-dashboard-title">Servicios de este mes</h2><p>{formatUtilityPeriod(period)}</p></div>
      <Link className="text-link" to={`/servicios?period=${period}`}>Ver servicios</Link>
    </div>
    {loading ? <LoadingState label="Cargando resumen de servicios…" /> : error ? (
      <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />
    ) : summary && <>
      <dl className="utility-totals" aria-label="Totales de servicios del mes">
        <div><dt>Pendiente · {summary.pending_count}</dt><dd>{formatMoney(summary.total_pending)}</dd></div>
        <div><dt>Pagado · {summary.paid_count}</dt><dd>{formatMoney(summary.total_paid)}</dd></div>
      </dl>
      {summary.pending_count + summary.paid_count === 0 && <p className="utility-help">Aún no hay montos registrados para este período. Entra a Servicios para registrar tu aporte.</p>}
      <p className="utility-help">Tus aportes por período del servicio, incluidos los de servicios archivados. Un pago de este período puede haberse realizado en otro mes.</p>
    </>}
  </section>;
}

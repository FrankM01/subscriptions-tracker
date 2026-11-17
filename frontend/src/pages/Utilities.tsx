import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { UtilityForm } from "../components/UtilityForms";
import { formatDate, formatMoney, todayInLima } from "../format";
import type { Utility, UtilityEntry, UtilityMonthlySummary } from "../types";
import { entryPeriod, latestUtilityPayment, parseUtilityPeriod } from "../utilities";

type Filter = "all" | "pending" | "paid" | "missing";

export function Utilities() {
  const [params, setParams] = useSearchParams();
  const period = parseUtilityPeriod(params.get("period")) ? params.get("period")! : todayInLima().slice(0, 7);
  const [utilities, setUtilities] = useState<Utility[]>([]);
  const [histories, setHistories] = useState<Record<string, UtilityEntry[]>>({});
  const [summary, setSummary] = useState<UtilityMonthlySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const { year, month } = parseUtilityPeriod(period)!;
    async function load() {
      try {
        const [catalog, totals] = await Promise.all([api.listUtilities(), api.getUtilityMonthlySummary(year, month)]);
        const entries = await Promise.all(catalog.map(async (utility) => [utility.utility_id, await api.listUtilityEntries(utility.utility_id)] as const));
        if (active) { setUtilities(catalog); setSummary(totals); setHistories(Object.fromEntries(entries)); }
      } catch (caught) {
        if (active) setError(caught instanceof ApiError ? caught.message : "No se pudieron cargar los servicios.");
      } finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [revision, period]);

  const rows = utilities.map((utility) => {
    const history = histories[utility.utility_id] ?? [];
    return { utility, current: history.find((entry) => entryPeriod(entry) === period), lastPayment: latestUtilityPayment(history) };
  }).filter(({ current }) => filter === "all" || (filter === "missing" ? !current : current?.status === filter));

  return <>
    <div className="page-heading">
      <div><h1>Servicios</h1><p>Luz, agua, internet y otros servicios de tu hogar. Aquí llevas el control de tu aporte personal.</p></div>
      <button className="button button-primary" type="button" disabled={creating} onClick={() => setCreating(true)}>Nuevo servicio</button>
    </div>
    {creating && <UtilityForm onCancel={() => setCreating(false)} onSaved={() => { setCreating(false); setRevision((value) => value + 1); }} />}
    <div className="utility-controls">
      <label className="field"><span>Mes de servicios</span><input type="month" required min="1900-01" max="9999-12" value={period} disabled={creating} onChange={(event) => { if (parseUtilityPeriod(event.target.value)) setParams({ period: event.target.value }); }} /></label>
      <label className="field"><span>Mostrar registros</span><select value={filter} onChange={(event) => setFilter(event.target.value as Filter)}>
        <option value="all">Todos</option><option value="pending">Pendientes</option><option value="paid">Pagados</option><option value="missing">Sin registro este mes</option>
      </select></label>
    </div>
    {loading ? <LoadingState label="Cargando servicios…" /> : error ? <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} /> : <>
      {summary && <dl className="utility-totals" aria-label="Resumen del período">
        <div><dt>Pendiente · {summary.pending_count}</dt><dd>{formatMoney(summary.total_pending)}</dd></div>
        <div><dt>Pagado · {summary.paid_count}</dt><dd>{formatMoney(summary.total_paid)}</dd></div>
      </dl>}
      <p className="utility-help">Importes por período del servicio. Incluyen los registros de servicios archivados; un mes sin registro no genera deuda.</p>
      {utilities.length === 0 ? <EmptyState title="Aún no tienes servicios registrados" message="Agrega tu primer servicio y registra el monto que te corresponde pagar." action={{ label: "Crear servicio", onClick: () => setCreating(true) }} /> :
        <section className="list-panel" aria-label="Catálogo de servicios">
          <div className="list-toolbar utility-catalog-toolbar"><h2>Mis servicios</h2><span className="results-count">{rows.length} {rows.length === 1 ? "servicio" : "servicios"}</span></div>
          {rows.length === 0 ? <EmptyState title="No hay registros con este filtro" message="Prueba otro estado o selecciona otro mes." /> : <ul className="utility-catalog">
            {rows.map(({ utility, current, lastPayment }) => <li className="utility-month-row" key={utility.utility_id}>
              <div className="utility-row-copy"><Link to={`/servicios/${utility.utility_id}?period=${period}`}><strong>{utility.name}</strong></Link>
                {utility.provider && <small>{utility.provider}</small>}
                <small>{utility.is_active ? "Activo" : "Archivado"}</small>
              </div>
              <div className="utility-row-copy utility-row-amount"><strong>{current ? formatMoney(current.amount) : "Sin registro"}</strong>
                <small>{current ? current.status === "paid" ? `Pagado el ${formatDate(current.paid_date!)}` : current.due_date ? `Vence el ${formatDate(current.due_date)}` : "Pendiente · sin vencimiento" : lastPayment ? `Último pago: ${formatMoney(lastPayment.amount)}` : "Aún no hay pagos anteriores"}</small>
              </div>
              <span className={`status-badge ${current?.status === "paid" ? "badge-active" : "badge-inactive"}`}>{current ? current.status === "paid" ? "Pagado" : "Pendiente" : "Sin registro"}</span>
              <Link className="button button-quiet button-small" aria-label={`Ver ${utility.name}`} to={`/servicios/${utility.utility_id}?period=${period}`}>Ver detalle</Link>
            </li>)}
          </ul>}
        </section>}
    </>}
  </>;
}

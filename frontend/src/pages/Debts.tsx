import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { DebtForm } from "../components/DebtForms";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { formatDate, formatMoney } from "../format";
import type { Debt } from "../types";
import { parseUtilityPeriod } from "../utilities";

export function Debts() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const period = parseUtilityPeriod(params.get("period")) ? params.get("period")! : "";
  const [debts, setDebts] = useState<Debt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [creating, setCreating] = useState(false);
  const [state, setState] = useState("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    api.listDebts().then((value) => { if (active) setDebts(value); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof ApiError ? caught.message : "No se pudieron cargar las deudas."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);

  const rows = debts.filter((debt) => (
    state === "all" || state === "active" && debt.is_active || state === "archived" && !debt.is_active
    || state === "pending" && debt.status === "pending" || state === "settled" && debt.status === "settled"
    || state === "overdue" && debt.overdue_installments > 0
  ) && (!period || debt.installments.some((row) => row.due_date.startsWith(period)))
    && `${debt.name} ${debt.creditor}`.toLocaleLowerCase("es").includes(query.trim().toLocaleLowerCase("es")));
  const detailLink = (id: string) => `/deudas/${id}${period ? `?period=${period}` : ""}`;

  return <>
    <div className="page-heading"><div><h1>Deudas</h1><p>Organiza tus préstamos y las cuotas que tienes por pagar.</p></div>
      <button className="button button-primary" type="button" disabled={creating} onClick={() => setCreating(true)}><Icon name="plus" />Nueva deuda</button>
    </div>
    {creating && <DebtForm onCancel={() => setCreating(false)} onSaved={(debt) => navigate(detailLink(debt.debt_id))} />}
    {loading ? <LoadingState label="Cargando deudas…" /> : error ? <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} /> : debts.length === 0 ?
      <EmptyState title="Aún no tienes deudas registradas" message="Registra un préstamo, su cuota mensual y cuántas cuotas ya pagaste." action={creating ? undefined : { label: "Registrar mi primera deuda", onClick: () => setCreating(true) }} /> : <>
      <div className="utility-controls debt-controls">
        <label className="field"><span>Buscar deuda o persona</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <label className="field"><span>Mostrar deudas</span><select value={state} onChange={(event) => setState(event.target.value)}>
          <option value="all">Todas</option><option value="active">Activas</option><option value="archived">Archivadas</option><option value="pending">Con saldo pendiente</option><option value="overdue">Con cuotas vencidas</option><option value="settled">Liquidadas</option>
        </select></label>
        <label className="field"><span>Mes de vencimiento (opcional)</span><input type="month" min="1900-01" max="9999-12" value={period} onChange={(event) => { const value = event.target.value; if (!value || parseUtilityPeriod(value)) setParams(value ? { period: value } : {}); }} /></label>
        {period && <button type="button" className="button button-quiet" onClick={() => setParams({})}>Ver todos los meses</button>}
      </div>
      <p className="utility-help">El avance y el saldo corresponden a toda la deuda. El filtro de mes muestra préstamos con alguna cuota que vence en ese período, pagada o pendiente.</p>
      <section className="list-panel" aria-label="Mis deudas">
        <div className="list-toolbar utility-catalog-toolbar"><h2>Mis préstamos</h2><span className="results-count">{rows.length} {rows.length === 1 ? "deuda" : "deudas"}</span></div>
        {rows.length === 0 ? <EmptyState title="No hay deudas con estos filtros" message="Prueba otra persona, otro estado o todos los meses." /> : <ul className="utility-catalog">{rows.map((debt) => <li className="utility-month-row debt-list-row" key={debt.debt_id}>
          <div className="utility-row-copy"><Link to={detailLink(debt.debt_id)}><strong>{debt.name}</strong></Link><small>A {debt.creditor}</small><small>{debt.paid_installments} de {debt.total_installments} cuotas pagadas · {debt.is_active ? "Activa" : "Archivada"}</small></div>
          <div className="utility-row-copy utility-row-amount"><strong>{formatMoney(debt.remaining_balance)} pendiente</strong><small>{debt.next_due_date ? `Próximo vencimiento: ${formatDate(debt.next_due_date)}` : "Sin cuotas pendientes"}</small>{debt.overdue_installments > 0 && <small className="debt-overdue">{debt.overdue_installments} {debt.overdue_installments === 1 ? "cuota vencida" : "cuotas vencidas"}</small>}</div>
          <span className={`status-badge ${debt.status === "settled" ? "badge-active" : "badge-inactive"}`}>{debt.status === "settled" ? "Liquidada" : "Pendiente"}</span>
          <Link className="button button-quiet button-small" to={detailLink(debt.debt_id)} aria-label={`Ver deuda ${debt.name}`}>Ver detalle</Link>
        </li>)}</ul>}
      </section>
    </>}
  </>;
}

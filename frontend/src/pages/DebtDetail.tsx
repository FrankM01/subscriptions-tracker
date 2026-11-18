import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { DebtForm, DebtPaymentForm } from "../components/DebtForms";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { formatDate, formatMoney, todayInLima } from "../format";
import type { Debt, DebtInstallment } from "../types";
import { parseUtilityPeriod } from "../utilities";

type Editor = { kind: "agreement" } | { kind: "confirm" | "correct" | "undo"; row: DebtInstallment } | null;

export function DebtDetail() {
  const { debtId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const period = parseUtilityPeriod(params.get("period")) ? params.get("period")! : "";
  const [debt, setDebt] = useState<Debt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<Editor>(null);
  const [status, setStatus] = useState("all");

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setEditor(null);
    api.getDebt(debtId).then((value) => { if (active) setDebt(value); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof ApiError ? caught.status === 404 || caught.status === 422 ? "No encontramos esta deuda." : caught.message : "No se pudo cargar la deuda."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [debtId, revision]);

  function saved() { setEditor(null); setActionError(""); setRevision((value) => value + 1); }
  async function toggleActive() {
    if (!debt || busy) return;
    setBusy(true); setActionError("");
    try { await api.updateDebt(debtId, { is_active: !debt.is_active }); saved(); }
    catch (caught) { setActionError(caught instanceof ApiError ? caught.message : "No se pudo actualizar la deuda."); }
    finally { setBusy(false); }
  }
  async function undo(row: DebtInstallment) {
    if (busy) return;
    setBusy(true); setActionError("");
    try { await api.undoDebtPayment(debtId, row.installment_id); saved(); }
    catch (caught) { setActionError(caught instanceof ApiError ? caught.message : "No se pudo deshacer el pago."); }
    finally { setBusy(false); }
  }

  const back = <Link className="back-link" to={`/deudas${period ? `?period=${period}` : ""}`}>Volver a deudas</Link>;
  if (loading) return <>{back}<LoadingState label="Cargando deuda…" /></>;
  if (error || !debt) return <>{back}<ErrorState message={error || "No encontramos esta deuda."} onRetry={() => setRevision((value) => value + 1)} /></>;
  const rows = debt.installments.filter((row) => (!period || row.due_date.startsWith(period))
    && (status === "all" || status === row.status || status === "overdue" && row.status === "pending" && row.due_date < todayInLima()));

  return <>
    {back}
    <div className="detail-heading">
      <div className="utility-detail-title"><h1>{debt.name}</h1><p>A {debt.creditor}</p><span className={`status-badge ${debt.status === "settled" ? "badge-active" : "badge-inactive"}`}>{debt.status === "settled" ? "Liquidada" : "Pendiente"}</span>{!debt.is_active && <span className="status-badge badge-inactive debt-archive-badge">Archivada</span>}</div>
      <div className="detail-actions"><button type="button" className="button button-quiet" disabled={!!editor || busy} onClick={() => setEditor({ kind: "agreement" })}>Editar deuda</button><button type="button" className="button button-quiet" disabled={!!editor || busy} onClick={() => void toggleActive()}>{busy ? "Guardando…" : debt.is_active ? "Archivar deuda" : "Reactivar deuda"}</button></div>
    </div>
    {actionError && <div className="form-error" role="alert">{actionError}</div>}
    {!debt.is_active && <p className="utility-notice">Deuda archivada. Sus cuotas pendientes y pagos se conservan; puedes seguir registrando pagos.</p>}
    <dl className="utility-totals debt-totals" aria-label="Estado de la deuda">
      <div><dt>Cuotas pagadas</dt><dd>{debt.paid_installments} de {debt.total_installments}</dd></div>
      <div><dt>Saldo pendiente</dt><dd>{formatMoney(debt.remaining_balance)}</dd></div>
      <div><dt>Cuota mensual</dt><dd>{formatMoney(debt.installment_amount)}</dd></div>
    </dl>
    <p className="utility-help">{debt.next_due_date ? `Próximo vencimiento pendiente: ${formatDate(debt.next_due_date)}.` : "Todas las cuotas están pagadas."} {debt.overdue_installments > 0 && <strong className="debt-overdue">{debt.overdue_installments} {debt.overdue_installments === 1 ? "cuota vencida" : "cuotas vencidas"}.</strong>}</p>
    {debt.previously_paid_installments > 0 && <p className="utility-notice">{debt.previously_paid_installments} {debt.previously_paid_installments === 1 ? "cuota previa declarada" : "cuotas previas declaradas"}. Se incluyen en el avance, sin inventar fechas ni pagos en el historial.</p>}
    {debt.notes && <p className="utility-notes debt-notes">{debt.notes}</p>}
    {editor?.kind === "agreement" && <DebtForm debt={debt} onCancel={() => setEditor(null)} onSaved={saved} />}
    {(editor?.kind === "confirm" || editor?.kind === "correct") && <DebtPaymentForm key={`${editor.kind}-${editor.row.installment_id}`} debtId={debtId} installment={editor.row} correction={editor.kind === "correct"} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "undo" && <section className="utility-editor" aria-label="Deshacer pago de cuota" tabIndex={-1} ref={(node) => { node?.focus(); }}>
      <h2>Deshacer pago de cuota {editor.row.number}</h2><p>La cuota volverá a pendiente por {formatMoney(editor.row.amount)}. Se conserva el vencimiento del {formatDate(editor.row.due_date)}.</p>
      <div className="form-actions"><button type="button" className="button button-quiet" disabled={busy} onClick={() => setEditor(null)}>Cancelar</button><button type="button" className="button button-primary" disabled={busy} onClick={() => void undo(editor.row)}>{busy ? "Procesando…" : "Volver a pendiente"}</button></div>
    </section>}
    <section className="history-panel utility-history debt-calendar" aria-label="Calendario de cuotas">
      <div className="panel-heading"><h2>Calendario de cuotas</h2><span className="count-pill">{debt.installments.length} registradas</span></div>
      <div className="utility-controls">
        <label className="field"><span>Mes de vencimiento (opcional)</span><input type="month" min="1900-01" max="9999-12" value={period} disabled={!!editor || busy} onChange={(event) => { const value = event.target.value; if (!value || parseUtilityPeriod(value)) setParams(value ? { period: value } : {}); }} /></label>
        <label className="field"><span>Mostrar cuotas</span><select value={status} disabled={!!editor || busy} onChange={(event) => setStatus(event.target.value)}><option value="all">Todas</option><option value="pending">Pendientes</option><option value="paid">Pagadas</option><option value="overdue">Vencidas</option></select></label>
        {period && <button type="button" className="button button-quiet" disabled={!!editor || busy} onClick={() => setParams({})}>Ver todos los meses</button>}
      </div>
      {debt.installments.length === 0 ? <EmptyState title="Sin cuotas por registrar" message="El avance previo declarado cubre todas las cuotas de esta deuda." /> : rows.length === 0 ? <EmptyState title="No hay cuotas con estos filtros" message="Selecciona otro estado o consulta todos los meses." /> : <ul className="utility-history-list">{rows.map((row) => <li className="utility-history-row" key={row.installment_id}>
        <div className="utility-row-copy"><strong>Cuota {row.number} de {debt.total_installments}</strong><small>Vencimiento: {formatDate(row.due_date)}</small><small className={row.status === "pending" && row.due_date < todayInLima() ? "debt-overdue" : ""}>{row.paid_date ? `Pagada el ${formatDate(row.paid_date)}` : row.due_date < todayInLima() ? "Pendiente · vencida" : "Pendiente"}</small></div>
        <strong className="utility-history-amount">{formatMoney(row.amount)}</strong>
        <div className="utility-entry-actions">{row.status === "pending" ? <button className="button button-primary button-small" type="button" disabled={!!editor || busy} onClick={() => setEditor({ kind: "confirm", row })}>Pagar cuota {row.number}</button> : <>
          <button className="button button-quiet button-small" type="button" disabled={!!editor || busy} onClick={() => setEditor({ kind: "correct", row })}>Corregir fecha de cuota {row.number}</button>
          <button className="button button-quiet button-small" type="button" disabled={!!editor || busy} onClick={() => { setActionError(""); setEditor({ kind: "undo", row }); }}>Deshacer pago de cuota {row.number}</button>
        </>}</div>
      </li>)}</ul>}
    </section>
  </>;
}

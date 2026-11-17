import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { UtilityEntryForm, UtilityForm, UtilityPaymentForm } from "../components/UtilityForms";
import { formatDate, formatMoney, todayInLima } from "../format";
import type { Utility, UtilityEntry } from "../types";
import { entryPeriod, formatUtilityPeriod, latestUtilityPayment, parseUtilityPeriod } from "../utilities";

type Editor = { kind: "service" } | { kind: "new" } | { kind: "edit" | "confirm" | "undo"; entry: UtilityEntry } | null;

export function UtilityDetail() {
  const { utilityId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const period = parseUtilityPeriod(params.get("period")) ? params.get("period")! : todayInLima().slice(0, 7);
  const [utility, setUtility] = useState<Utility | null>(null);
  const [history, setHistory] = useState<UtilityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<Editor>(null);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setEditor(null);
    Promise.all([api.getUtility(utilityId), api.listUtilityEntries(utilityId)]).then(([catalogItem, entries]) => {
      if (active) { setUtility(catalogItem); setHistory(entries); }
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof ApiError ? caught.status === 404 || caught.status === 422 ? "No encontramos este servicio." : caught.message : "No se pudo cargar el servicio.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [utilityId, revision]);

  function saved() { setEditor(null); setActionError(""); setRevision((value) => value + 1); }
  async function toggleActive() {
    if (!utility || busy) return;
    setBusy(true); setActionError("");
    try { await api.updateUtility(utilityId, { is_active: !utility.is_active }); saved(); }
    catch (caught) { setActionError(caught instanceof ApiError ? caught.message : "No se pudo actualizar el servicio."); }
    finally { setBusy(false); }
  }
  async function undo(entry: UtilityEntry) {
    if (busy) return;
    setBusy(true); setActionError("");
    try { await api.undoUtilityPayment(utilityId, entry.entry_id); saved(); }
    catch (caught) { setActionError(caught instanceof ApiError ? caught.message : "No se pudo deshacer el pago."); }
    finally { setBusy(false); }
  }

  const back = <Link className="back-link" to={`/servicios?period=${period}`}>Volver a servicios</Link>;
  if (loading) return <>{back}<LoadingState label="Cargando servicio…" /></>;
  if (error || !utility) return <>{back}<ErrorState message={error || "No encontramos este servicio."} onRetry={() => setRevision((value) => value + 1)} /></>;
  const current = history.find((entry) => entryPeriod(entry) === period);
  const lastPayment = latestUtilityPayment(history);

  function entryActions(entry: UtilityEntry) {
    return <div className="utility-entry-actions">
      <button className="button button-quiet button-small" type="button" disabled={!!editor || busy} onClick={() => setEditor({ kind: "edit", entry })}>Corregir registro</button>
      {entry.status === "pending" ? <button className="button button-primary button-small" type="button" disabled={!!editor || busy} onClick={() => setEditor({ kind: "confirm", entry })}>Confirmar pago</button> :
        <button className="button button-quiet button-small" type="button" disabled={!!editor || busy} onClick={() => { setActionError(""); setEditor({ kind: "undo", entry }); }}>Deshacer pago</button>}
    </div>;
  }

  return <>
    {back}
    <div className="detail-heading">
      <div className="utility-detail-title"><h1>{utility.name}</h1>{utility.provider && <p>{utility.provider}</p>}<span className={`status-badge ${utility.is_active ? "badge-active" : "badge-inactive"}`}>{utility.is_active ? "Activo" : "Archivado"}</span></div>
      <div className="detail-actions">
        <button className="button button-quiet" type="button" disabled={!!editor || busy} onClick={() => setEditor({ kind: "service" })}>Editar servicio</button>
        <button className="button button-quiet" type="button" disabled={!!editor || busy} onClick={() => void toggleActive()}>{busy ? "Guardando…" : utility.is_active ? "Archivar servicio" : "Reactivar servicio"}</button>
      </div>
    </div>
    {actionError && <div className="form-error" role="alert">{actionError}</div>}
    {!utility.is_active && <p className="utility-notice">Servicio archivado. Puedes corregir o pagar períodos existentes. Reactívalo para registrar otro mes; su historial se conserva.</p>}
    {editor?.kind === "service" && <UtilityForm utility={utility} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "new" && <UtilityEntryForm key={`new-${period}`} utilityId={utilityId} period={period} lastPayment={lastPayment} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "edit" && <UtilityEntryForm key={editor.entry.entry_id} utilityId={utilityId} period={period} entry={editor.entry} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "confirm" && <UtilityPaymentForm utilityId={utilityId} entry={editor.entry} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "undo" && <section className="utility-editor" aria-label="Deshacer pago">
      <h2>Deshacer pago de {formatUtilityPeriod(entryPeriod(editor.entry))}</h2>
      <p>El registro volverá a pendiente. Se conservarán el período, el monto de {formatMoney(editor.entry.amount)} y las notas.</p>
      <div className="form-actions"><button className="button button-quiet" type="button" disabled={busy} onClick={() => setEditor(null)}>Cancelar</button><button className="button button-primary" type="button" disabled={busy} onClick={() => void undo(editor.entry)}>{busy ? "Procesando…" : "Volver a pendiente"}</button></div>
    </section>}
    <section className="utility-period-panel" aria-label="Período seleccionado">
      <label className="field"><span>Período del servicio</span><input type="month" min="1900-01" max="9999-12" required disabled={!!editor || busy} value={period} onChange={(event) => { if (parseUtilityPeriod(event.target.value)) setParams({ period: event.target.value }); }} /></label>
      {current ? <div className="utility-current"><div><strong>{formatMoney(current.amount)}</strong><p>{current.status === "paid" ? `Pagado el ${formatDate(current.paid_date!)}` : current.due_date ? `Pendiente · vence el ${formatDate(current.due_date)}` : "Pendiente · sin vencimiento"}</p></div>{entryActions(current)}</div> : <div className="utility-current"><p>Sin registro para {formatUtilityPeriod(period)}.</p><button className="button button-primary" type="button" disabled={!utility.is_active || !!editor || busy} onClick={() => setEditor({ kind: "new" })}>Registrar mi monto</button></div>}
      {!current && lastPayment && <p className="utility-help">Último pago: {formatMoney(lastPayment.amount)} · {formatUtilityPeriod(entryPeriod(lastPayment))}, pagado el {formatDate(lastPayment.paid_date!)}. Solo como referencia.</p>}
    </section>
    <section className="history-panel utility-history" aria-label="Historial de servicios">
      <div className="panel-heading"><h2>Historial por mes</h2><span className="count-pill">{history.length} {history.length === 1 ? "registro" : "registros"}</span></div>
      {history.length === 0 ? <EmptyState title="Aún no hay registros mensuales" message="Elige el período y registra tu aporte. Los meses anteriores permanecerán aquí." /> : <ul className="utility-history-list">{history.map((entry) => <li className="utility-history-row" key={entry.entry_id}>
        <div className="utility-row-copy"><strong>{formatUtilityPeriod(entryPeriod(entry))}</strong><small>{entry.status === "paid" ? `Pagado el ${formatDate(entry.paid_date!)}` : entry.due_date ? `Pendiente · vence el ${formatDate(entry.due_date)}` : "Pendiente · sin vencimiento"}</small>{entry.notes && <p className="utility-notes">{entry.notes}</p>}</div>
        <strong className="utility-history-amount">{formatMoney(entry.amount)}</strong>
        {entryPeriod(entry) !== period && entryActions(entry)}
      </li>)}</ul>}
    </section>
  </>;
}

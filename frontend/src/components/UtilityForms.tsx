import { useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { formatMoney, todayInLima } from "../format";
import type { Utility, UtilityEntry } from "../types";
import { entryPeriod, formatUtilityPeriod, parseUtilityPeriod, personalAmount } from "../utilities";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo guardar. Intenta nuevamente.";
}

function FormPanel({ title, busy, error, onSubmit, onCancel, children, submitLabel }: {
  title: string; busy: boolean; error: string; onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void; children: ReactNode; submitLabel: string;
}) {
  return <section className="utility-editor" aria-label={title}>
    <h2>{title}</h2>
    <form onSubmit={onSubmit}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <fieldset className="utility-fields form-stack" disabled={busy}>
        <legend className="sr-only">{title}</legend>
        {children}
        <div className="form-actions">
          <button className="button button-quiet" onClick={onCancel} type="button">Cancelar</button>
          <button className="button button-primary" type="submit">{busy ? "Guardando…" : submitLabel}</button>
        </div>
      </fieldset>
    </form>
  </section>;
}

export function UtilityForm({ utility, onCancel, onSaved }: {
  utility?: Utility; onCancel: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(utility?.name ?? "");
  const [provider, setProvider] = useState(utility?.provider ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) { setError("Escribe el nombre del servicio."); return; }
    setBusy(true); setError("");
    try {
      const input = { name: name.trim(), provider: provider.trim() || null };
      if (utility) await api.updateUtility(utility.utility_id, input);
      else await api.createUtility(input);
      onSaved();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(false); }
  }
  return <FormPanel title={utility ? "Editar servicio" : "Nuevo servicio"} busy={busy} error={error}
    onSubmit={(event) => void submit(event)} onCancel={onCancel} submitLabel={utility ? "Guardar servicio" : "Crear servicio"}>
    <label className="field"><span>Nombre del servicio</span><input autoFocus required value={name} onChange={(event) => setName(event.target.value)} placeholder="Ej. Luz" /></label>
    <label className="field"><span>Proveedor (opcional)</span><input value={provider} onChange={(event) => setProvider(event.target.value)} /></label>
  </FormPanel>;
}

export function UtilityEntryForm({ utilityId, period, entry, lastPayment, onCancel, onSaved }: {
  utilityId: string; period: string; entry?: UtilityEntry; lastPayment?: UtilityEntry;
  onCancel: () => void; onSaved: () => void;
}) {
  const [selectedPeriod, setSelectedPeriod] = useState(entry ? entryPeriod(entry) : period);
  const [amount, setAmount] = useState(entry?.amount ?? "");
  const [dueDate, setDueDate] = useState(entry?.due_date ?? "");
  const [paid, setPaid] = useState(entry?.status === "paid");
  const [paidDate, setPaidDate] = useState(entry?.paid_date ?? todayInLima());
  const [notes, setNotes] = useState(entry?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const parsed = parseUtilityPeriod(selectedPeriod);
    const normalized = personalAmount(amount);
    if (!parsed) { setError("Selecciona un mes y año válidos desde 1900."); return; }
    if (!normalized) { setError("Ingresa tu monto mayor a cero, con hasta dos decimales y un máximo de S/ 9,999,999.99."); return; }
    if (paid && (!paidDate || paidDate > todayInLima())) { setError("La fecha de pago debe ser hoy o una fecha anterior."); return; }
    setBusy(true); setError("");
    try {
      const input = { ...parsed, amount: normalized, due_date: dueDate || null, notes: notes.trim() || null };
      if (entry) await api.updateUtilityEntry(utilityId, entry.entry_id, { ...input, ...(paid ? { paid_date: paidDate } : {}) });
      else await api.createUtilityEntry(utilityId, { ...input, paid_date: paid ? paidDate : null });
      onSaved();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(false); }
  }
  return <FormPanel title={entry ? "Corregir registro mensual" : "Registrar mi monto"} busy={busy} error={error}
    onSubmit={(event) => void submit(event)} onCancel={onCancel} submitLabel={entry ? "Guardar registro" : "Registrar monto"}>
    <div className="form-grid">
      <label className="field"><span>Período del servicio</span><input autoFocus required type="month" min="1900-01" max="9999-12" value={selectedPeriod} onChange={(event) => setSelectedPeriod(event.target.value)} /></label>
      <label className="field"><span>Mi monto (S/)</span><input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /></label>
    </div>
    {!entry && lastPayment && <p className="utility-help">Último pago: {formatMoney(lastPayment.amount)} · {formatUtilityPeriod(entryPeriod(lastPayment))}. Ingresa el monto que te corresponde ahora.</p>}
    <label className="field"><span>Vencimiento (opcional)</span><input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label>
    {!entry && <label className="utility-checkbox"><input checked={paid} type="checkbox" onChange={(event) => setPaid(event.target.checked)} />Ya pagué este período</label>}
    {paid && <label className="field"><span>Fecha real del pago</span><input type="date" required max={todayInLima()} value={paidDate} onChange={(event) => setPaidDate(event.target.value)} /></label>}
    {entry && <p className="utility-help">{paid ? "Este registro seguirá pagado. Usa Deshacer pago para volver a pendiente." : "Este registro seguirá pendiente. Usa Confirmar pago cuando lo realices."}</p>}
    <label className="field"><span>Notas (opcional)</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
  </FormPanel>;
}

export function UtilityPaymentForm({ utilityId, entry, onCancel, onSaved }: {
  utilityId: string; entry: UtilityEntry; onCancel: () => void; onSaved: () => void;
}) {
  const [amount, setAmount] = useState(entry.amount);
  const [paidDate, setPaidDate] = useState(todayInLima());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const normalized = personalAmount(amount);
    if (!normalized) { setError("Ingresa un monto positivo con hasta dos decimales (máximo S/ 9,999,999.99)."); return; }
    if (!paidDate || paidDate > todayInLima()) { setError("La fecha de pago no puede estar en el futuro."); return; }
    setBusy(true); setError("");
    try {
      await api.confirmUtilityPayment(utilityId, entry.entry_id, { amount: normalized, paid_date: paidDate });
      onSaved();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(false); }
  }
  return <FormPanel title="Confirmar pago" busy={busy} error={error} onSubmit={(event) => void submit(event)} onCancel={onCancel} submitLabel="Guardar pago">
    <p className="utility-help">Período del servicio: {formatUtilityPeriod(entryPeriod(entry))}. La fecha del pago puede pertenecer a otro mes.</p>
    <label className="field"><span>Monto que pagué (S/)</span><input autoFocus required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
    <label className="field"><span>Fecha real del pago</span><input type="date" required max={todayInLima()} value={paidDate} onChange={(event) => setPaidDate(event.target.value)} /></label>
  </FormPanel>;
}

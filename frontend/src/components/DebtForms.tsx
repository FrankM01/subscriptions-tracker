import { useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { formatDate, formatMoney, todayInLima } from "../format";
import type { Debt, DebtInstallment } from "../types";
import { personalAmount } from "../utilities";

function message(error: unknown): string {
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
          <button className="button button-quiet" type="button" onClick={onCancel}>Cancelar</button>
          <button className="button button-primary" type="submit">{busy ? "Guardando…" : submitLabel}</button>
        </div>
      </fieldset>
    </form>
  </section>;
}

export function DebtForm({ debt, onCancel, onSaved }: {
  debt?: Debt; onCancel: () => void; onSaved: (value: Debt) => void;
}) {
  const [name, setName] = useState(debt?.name ?? "");
  const [creditor, setCreditor] = useState(debt?.creditor ?? "");
  const [amount, setAmount] = useState(debt?.installment_amount ?? "");
  const [total, setTotal] = useState(String(debt?.total_installments ?? 6));
  const [previous, setPrevious] = useState(String(debt?.previously_paid_installments ?? 0));
  const [firstDate, setFirstDate] = useState(debt?.first_due_date ?? "");
  const [notes, setNotes] = useState(debt?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const editable = !debt || debt.schedule_editable;
  const count = Number(total) - Number(previous);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim() || !creditor.trim()) { setError("Escribe el nombre de la deuda y la persona a quien pagarás."); return; }
    const normalized = personalAmount(amount);
    if (editable) {
      if (!normalized) { setError("Ingresa una cuota positiva de hasta dos decimales y S/ 9,999,999.99."); return; }
      if (!total || !previous || !Number.isSafeInteger(Number(total)) || !Number.isSafeInteger(Number(previous)) || Number(total) < 1 || Number(total) > 2147483647 || Number(previous) < 0 || count < 0) {
        setError("Revisa el total de cuotas y el avance previo: las pagadas no pueden superar al total."); return;
      }
      if (count > 0) {
        if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(firstDate)) { setError("Indica el primer vencimiento pendiente."); return; }
        const [year, month] = firstDate.split("-").map(Number);
        if (year < 1 || (year - 1) * 12 + month - 1 + count - 1 >= 9999 * 12) { setError("El calendario de cuotas supera el año 9999."); return; }
      }
    }
    setBusy(true); setError("");
    try {
      const metadata = { name: name.trim(), creditor: creditor.trim(), notes: notes.trim() || null };
      const schedule = {
        installment_amount: normalized!, total_installments: Number(total),
        previously_paid_installments: Number(previous), first_due_date: count > 0 ? firstDate : null,
      };
      const saved = debt
        ? await api.updateDebt(debt.debt_id, { ...metadata, ...(editable ? schedule : {}) })
        : await api.createDebt({ ...metadata, ...schedule });
      onSaved(saved);
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }

  return <FormPanel title={debt ? "Editar deuda" : "Nueva deuda"} busy={busy} error={error}
    onSubmit={(event) => void submit(event)} onCancel={onCancel} submitLabel={debt ? "Guardar deuda" : "Crear deuda"}>
    <label className="field"><span>Nombre de la deuda</span><input autoFocus required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} placeholder="Ej. Préstamo para estudios" /></label>
    <label className="field"><span>Persona a quien debo</span><input required maxLength={200} value={creditor} onChange={(event) => setCreditor(event.target.value)} placeholder="Nombre del acreedor" /></label>
    {editable ? <>
      <label className="field"><span>Importe de cada cuota (S/)</span><input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /><small>Importe fijo ya acordado. No se calculan intereses.</small></label>
      <div className="form-grid">
        <label className="field"><span>Total de cuotas</span><input required type="number" min="1" max="2147483647" step="1" value={total} onChange={(event) => setTotal(event.target.value)} /></label>
        <label className="field"><span>Cuotas pagadas antes de usar la app</span><input required type="number" min="0" max={total || undefined} step="1" value={previous} onChange={(event) => setPrevious(event.target.value)} /></label>
      </div>
      <p className="utility-help">El avance previo no crea pagos ni fechas en el historial. Por ejemplo, 1 pagada de 6 deja las cuotas 2 a 6 por registrar.</p>
      {count > 0 && <label className="field"><span>Primer vencimiento pendiente</span><input required type="date" min="0001-01-01" max="9999-12-31" value={firstDate} onChange={(event) => setFirstDate(event.target.value)} /><small>Es la fecha de la cuota {Number(previous) + 1}. Puede estar vencida; las siguientes se programan cada mes.</small></label>}
      {count >= 0 && total !== "" && previous !== "" && <p className="utility-notice">{count === 0 ? "La deuda quedará liquidada, sin cuotas pendientes." : `Se ${debt ? "programarán" : "crearán"} ${count} cuotas pendientes, de la ${Number(previous) + 1} a la ${Number(total)}.`}</p>}
      {debt && <p className="utility-help">Cambiar el importe, el plazo o el avance previo reconstruye el calendario. No hay pagos confirmados que se puedan perder.</p>}
    </> : <p className="utility-notice">Acuerdo con pagos confirmados: {debt.total_installments} cuotas de {formatMoney(debt.installment_amount)}. El calendario y el importe están bloqueados; puedes editar nombre, acreedor y notas.</p>}
    <label className="field"><span>Notas (opcional)</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
  </FormPanel>;
}

export function DebtPaymentForm({ debtId, installment, correction = false, onCancel, onSaved }: {
  debtId: string; installment: DebtInstallment; correction?: boolean; onCancel: () => void; onSaved: () => void;
}) {
  const [paidDate, setPaidDate] = useState(correction ? installment.paid_date ?? todayInLima() : todayInLima());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!paidDate || paidDate > todayInLima()) { setError("La fecha real del pago debe ser hoy o una fecha anterior."); return; }
    setBusy(true); setError("");
    try {
      if (correction) await api.correctDebtPayment(debtId, installment.installment_id, paidDate);
      else await api.confirmDebtPayment(debtId, installment.installment_id, paidDate);
      onSaved();
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }
  return <FormPanel title={`${correction ? "Corregir fecha de" : "Pagar"} cuota ${installment.number}`} busy={busy} error={error}
    onSubmit={(event) => void submit(event)} onCancel={onCancel} submitLabel={correction ? "Guardar fecha" : "Confirmar pago completo"}>
    <p className="utility-help">Cuota {installment.number} · {formatMoney(installment.amount)} · vence el {formatDate(installment.due_date)}. {correction ? "El pago seguirá confirmado." : "Se registrará el importe completo. Puedes pagar antes del vencimiento."}</p>
    <label className="field"><span>Fecha real del pago</span><input autoFocus required type="date" max={todayInLima()} value={paidDate} onChange={(event) => setPaidDate(event.target.value)} /></label>
  </FormPanel>;
}

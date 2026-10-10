import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { formatDate, todayInLima } from "../format";
import type { Subscription } from "../types";
import { Icon } from "./Icon";
import { Modal } from "./Modal";

export function RenewalConfirmationModal({
  subscription,
  onClose,
  onSaved,
}: {
  subscription: Subscription;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [paidDate, setPaidDate] = useState(todayInLima());
  const [paidAmount, setPaidAmount] = useState(subscription.cost);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.confirmRenewal(subscription.subscription_id, {
        scheduled_date: subscription.renewal_date,
        paid_date: paidDate,
        paid_amount: paidAmount,
      });
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo registrar el cobro.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Confirmar cobro" eyebrow="REGISTRA UN PERÍODO" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <div className="renewal-period-note">
          <span className="notice-icon"><Icon name="calendar" /></span>
          <span>Estás confirmando el período previsto para <strong>{formatDate(subscription.renewal_date)}</strong>.</span>
        </div>
        {error && <div className="form-error" role="alert">{error}<small>Actualiza los datos de la página antes de volver a intentarlo.</small></div>}
        <div className="form-grid">
          <label className="field">
            <span>Fecha en que pagaste</span>
            <input max={todayInLima()} onChange={(event) => setPaidDate(event.target.value)} required type="date" value={paidDate} />
          </label>
          <label className="field">
            <span>Importe pagado</span>
            <div className="input-with-prefix"><span>S/</span><input inputMode="decimal" min="0.01" onChange={(event) => setPaidAmount(event.target.value)} required step="0.01" type="number" value={paidAmount} /></div>
          </label>
        </div>
        <p className="form-hint">La próxima fecha avanzará un período desde la fecha prevista, aunque el pago haya sido tardío.</p>
        <div className="form-actions">
          <button className="button button-quiet" onClick={onClose} type="button">Cancelar</button>
          <button className="button button-primary" disabled={busy || Number(paidAmount) <= 0 || !paidDate || paidDate > todayInLima()} type="submit">
            <Icon name="check" />{busy ? "Registrando…" : "Confirmar cobro"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { addCalendarDays, todayInLima } from "../format";
import type { BillingCycle, Subscription, SubscriptionInput, SubscriptionUpdateInput } from "../types";
import { Icon } from "./Icon";
import { Modal } from "./Modal";

export function SubscriptionFormModal({
  subscription,
  onClose,
  onSaved,
}: {
  subscription?: Subscription;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(subscription?.name ?? "");
  const [cost, setCost] = useState(subscription?.cost ?? "");
  const [billingCycle, setBillingCycle] = useState<BillingCycle>(subscription?.billing_cycle ?? "monthly");
  const [renewalDate, setRenewalDate] = useState(subscription?.renewal_date ?? "");
  const [renewalDateTouched, setRenewalDateTouched] = useState(false);
  const [isActive, setIsActive] = useState(subscription?.is_active ?? true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const minDate = addCalendarDays(todayInLima(), 1);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (subscription && !subscription.is_active && isActive && !renewalDateTouched) {
      setError("Al reactivar, revisa y selecciona la próxima fecha de cobro.");
      return;
    }
    if (subscription && !subscription.is_active && isActive && renewalDate < minDate) {
      setError("La fecha revisada debe ser futura.");
      return;
    }

    const input: SubscriptionUpdateInput = {};
    if (subscription) {
      if (name.trim() !== subscription.name) input.name = name.trim();
      if (cost !== subscription.cost) input.cost = cost;
      if (billingCycle !== subscription.billing_cycle) input.billing_cycle = billingCycle;
      if (renewalDateTouched) input.renewal_date = renewalDate;
      if (isActive !== subscription.is_active) input.is_active = isActive;
      if (Object.keys(input).length === 0) {
        setError("No hay cambios para guardar.");
        return;
      }
    }
    setBusy(true);
    try {
      if (subscription) {
        await api.updateSubscription(subscription.subscription_id, input);
      } else {
        const newSubscription: SubscriptionInput = {
          name: name.trim(),
          cost,
          billing_cycle: billingCycle,
          renewal_date: renewalDate,
          is_active: isActive,
        };
        await api.createSubscription(newSubscription);
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo guardar la suscripción.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={subscription ? "Editar suscripción" : "Nueva suscripción"}
      eyebrow={subscription ? "ACTUALIZA TUS DATOS" : "AGREGA UN COBRO RECURRENTE"}
      onClose={onClose}
    >
      <form className="form-stack" onSubmit={submit}>
        {error && <div className="form-error" role="alert">{error}</div>}
        <label className="field">
          <span>Nombre</span>
          <input autoFocus maxLength={100} onChange={(event) => setName(event.target.value)} placeholder="Ej. Plataforma de música" required value={name} />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Precio</span>
            <div className="input-with-prefix"><span>S/</span><input inputMode="decimal" min="0.01" onChange={(event) => setCost(event.target.value)} placeholder="0.00" required step="0.01" type="number" value={cost} /></div>
          </label>
          <label className="field">
            <span>Frecuencia</span>
            <select onChange={(event) => setBillingCycle(event.target.value as BillingCycle)} value={billingCycle}>
              <option value="monthly">Mensual</option>
              <option value="yearly">Anual</option>
            </select>
          </label>
        </div>
        <label className="field">
          <span>Próxima fecha de cobro</span>
          <input min={!subscription || renewalDateTouched ? minDate : undefined} onChange={(event) => { setRenewalDate(event.target.value); setRenewalDateTouched(true); }} required type="date" value={renewalDate} />
          <small>Debe ser futura al crear o cambiar la fecha. Para reactivar, selecciona la próxima fecha aunque quieras conservar la actual.</small>
        </label>
        <label className="toggle-field">
          <span className="toggle-copy"><strong>Suscripción activa</strong><small>Las inactivas no aparecen en el gasto ni en los avisos.</small></span>
          <input checked={isActive} onChange={(event) => setIsActive(event.target.checked)} type="checkbox" />
          <span className="toggle-control" aria-hidden="true" />
        </label>
        <div className="form-actions">
          <button className="button button-quiet" onClick={onClose} type="button">Cancelar</button>
          <button className="button button-primary" disabled={busy || cost === "" || Number(cost) <= 0 || !renewalDate || ((!subscription || renewalDateTouched) && renewalDate < minDate)} type="submit">
            <Icon name="check" />{busy ? "Guardando…" : subscription ? "Guardar cambios" : "Crear suscripción"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { ConfirmDialog } from "../components/Modal";
import { RenewalConfirmationModal } from "../components/RenewalConfirmationModal";
import { SubscriptionFormModal } from "../components/SubscriptionForm";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { formatDate, formatMoney } from "../format";
import type { RenewalEntry, Subscription } from "../types";

export function SubscriptionDetail() {
  const { subscriptionId = "" } = useParams();
  const navigate = useNavigate();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [renewals, setRenewals] = useState<RenewalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [modal, setModal] = useState<"confirm" | "edit" | "undo" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [subscriptions, history] = await Promise.all([
        api.listSubscriptions(), api.listRenewals(subscriptionId),
      ]);
      const found = subscriptions.find((item) => item.subscription_id === subscriptionId);
      if (!found) throw new ApiError(404, "No encontramos esta suscripción.");
      setSubscription(found);
      setRenewals(history);
    } catch (caught) {
      if (caught instanceof ApiError && (caught.status === 404 || caught.status === 422)) {
        setError("No encontramos esta suscripción.");
      } else {
        setError(caught instanceof ApiError ? caught.message : "No se pudo cargar el detalle.");
      }
    } finally {
      setLoading(false);
    }
  }, [subscriptionId]);

  useEffect(() => { void load(); }, [load]);

  async function refreshAndClose() {
    setModal(null);
    setActionError("");
    await load();
  }

  async function undoLatest() {
    setBusy(true);
    setActionError("");
    try {
      await api.undoRenewal(subscriptionId);
      setModal(null);
      await load();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "No se pudo deshacer el cobro.");
      setModal(null);
    } finally {
      setBusy(false);
    }
  }

  async function deletePermanently() {
    setBusy(true);
    setActionError("");
    try {
      await api.deleteSubscription(subscriptionId);
      navigate("/suscripciones", { replace: true });
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "No se pudo eliminar la suscripción.");
      setModal(null);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    if (!subscription) return;
    if (!subscription.is_active) {
      setModal("edit");
      return;
    }
    setBusy(true);
    setActionError("");
    try {
      await api.updateSubscription(subscriptionId, { is_active: false });
      await load();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "No se pudo actualizar el estado.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingState label="Cargando detalle…" />;
  if (error || !subscription) return <><Link className="back-link" to="/suscripciones">← Volver a suscripciones</Link><ErrorState message={error || "No encontramos esta suscripción."} onRetry={() => void load()} /></>;

  return (
    <>
      <Link className="back-link" to="/suscripciones">← Todas las suscripciones</Link>
      <div className="detail-heading">
        <div className="detail-title-group"><span className="service-avatar avatar-large">{subscription.name.trim().charAt(0).toUpperCase() || "S"}</span><div><div className="eyebrow">DETALLE DE SUSCRIPCIÓN</div><h1>{subscription.name}</h1><span className={`status-badge ${subscription.is_active ? "badge-active" : "badge-inactive"}`}><span />{subscription.is_active ? "Activa" : "Inactiva"}</span></div></div>
        <div className="detail-actions">
          <button className="button button-quiet" onClick={() => setModal("edit")} type="button">Editar</button>
          <button className="button button-quiet" disabled={busy} onClick={() => void toggleActive()} type="button">{busy ? "Guardando…" : subscription.is_active ? "Desactivar" : "Reactivar"}</button>
          <button className="button button-danger-quiet" onClick={() => setModal("delete")} type="button">Eliminar</button>
        </div>
      </div>
      {actionError && <div className="inline-error" role="alert">{actionError}<button aria-label="Cerrar mensaje" onClick={() => setActionError("")} type="button"><Icon name="close" /></button></div>}

      <section className="detail-overview">
        <div className="detail-metric"><span>Precio</span><strong>{formatMoney(subscription.cost)}</strong><small>por {subscription.billing_cycle === "monthly" ? "mes" : "año"}</small></div>
        <div className="detail-metric"><span>Frecuencia</span><strong>{subscription.billing_cycle === "monthly" ? "Mensual" : "Anual"}</strong><small>cobro recurrente</small></div>
        <div className="detail-metric renewal-metric"><span>Próxima fecha pendiente</span><strong><Icon name="calendar" />{formatDate(subscription.renewal_date)}</strong><small>El cobro no se registra automáticamente</small></div>
        {subscription.is_active && <button className="button button-primary detail-confirm" onClick={() => setModal("confirm")} type="button"><Icon name="check" />Confirmar cobro</button>}
      </section>

      <section className="history-panel">
        <div className="panel-heading"><div><div className="eyebrow">REGISTRO DE PAGOS</div><h2>Historial</h2></div><span className="count-pill">{renewals.length} {renewals.length === 1 ? "pago" : "pagos"}</span></div>
        {renewals.length === 0 ? <EmptyState title="Aún no hay pagos registrados" message="Cuando confirmes una renovación, aparecerá aquí con su fecha e importe pagados." /> : (
          <div className="history-list">{renewals.map((renewal, index) => <article className="history-row" key={renewal.renewal_id}>
            <span className="history-check"><Icon name="check" /></span>
            <div className="history-description"><strong>{formatDate(renewal.scheduled_date)}</strong><small>Período previsto · pagado el {formatDate(renewal.paid_date)}</small></div>
            <strong className="history-amount">{formatMoney(renewal.paid_amount)}</strong>
            {index === 0 && <button className="button button-quiet button-small undo-button" onClick={() => setModal("undo")} type="button">Deshacer último</button>}
          </article>)}</div>
        )}
      </section>
      {modal === "edit" && <SubscriptionFormModal subscription={subscription} onClose={() => setModal(null)} onSaved={() => void refreshAndClose()} />}
      {modal === "confirm" && <RenewalConfirmationModal subscription={subscription} onClose={() => setModal(null)} onSaved={() => void refreshAndClose()} />}
      {modal === "undo" && <ConfirmDialog
        title="Deshacer último cobro"
        message="Se quitará el último pago del historial y se restaurará su fecha pendiente anterior."
        confirmLabel="Deshacer cobro"
        busy={busy}
        onCancel={() => setModal(null)}
        onConfirm={() => void undoLatest()}
      />}
      {modal === "delete" && <ConfirmDialog
        title="Eliminar suscripción"
        message={`Se eliminará ${subscription.name} y todo su historial. Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar definitivamente"
        destructive
        busy={busy}
        onCancel={() => setModal(null)}
        onConfirm={() => void deletePermanently()}
      />}
    </>
  );
}

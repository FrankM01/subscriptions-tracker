import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { ConfirmDialog } from "../components/Modal";
import { SubscriptionFormModal } from "../components/SubscriptionForm";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { formatDate, formatMoney } from "../format";
import type { Subscription } from "../types";

type Filter = "all" | "active" | "inactive";

export function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formSubscription, setFormSubscription] = useState<Subscription | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Subscription | null>(null);
  const [busyId, setBusyId] = useState("");
  const [actionError, setActionError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSubscriptions(await api.listSubscriptions());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo cargar la lista.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const counts = useMemo(() => ({
    all: subscriptions.length,
    active: subscriptions.filter((subscription) => subscription.is_active).length,
    inactive: subscriptions.filter((subscription) => !subscription.is_active).length,
  }), [subscriptions]);
  const visibleSubscriptions = subscriptions.filter((subscription) =>
    filter === "all" || (filter === "active" ? subscription.is_active : !subscription.is_active),
  );

  async function toggleActive(subscription: Subscription) {
    if (!subscription.is_active) {
      setFormSubscription(subscription);
      return;
    }
    setActionError("");
    setBusyId(subscription.subscription_id);
    try {
      await api.updateSubscription(subscription.subscription_id, { is_active: false });
      await load();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "No se pudo actualizar el estado.");
    } finally {
      setBusyId("");
    }
  }

  async function removeSubscription() {
    if (!deleting) return;
    setActionError("");
    setBusyId(deleting.subscription_id);
    try {
      await api.deleteSubscription(deleting.subscription_id);
      setDeleting(null);
      await load();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "No se pudo eliminar la suscripción.");
    } finally {
      setBusyId("");
    }
  }

  function saved() {
    setFormSubscription(undefined);
    void load();
  }

  return (
    <>
      <div className="page-heading">
        <div><div className="eyebrow">TUS SERVICIOS</div><h1>Suscripciones</h1><p>Organiza tus cobros recurrentes en un solo lugar.</p></div>
        <button className="button button-primary" onClick={() => setFormSubscription(null)} type="button"><Icon name="plus" />Nueva suscripción</button>
      </div>
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {actionError && <div className="inline-error" role="alert">{actionError}<button aria-label="Cerrar mensaje" onClick={() => setActionError("")} type="button"><Icon name="close" /></button></div>}
      <section className="list-panel" aria-label="Lista de suscripciones">
        <div className="list-toolbar">
          <div className="filter-tabs" aria-label="Filtrar suscripciones" role="tablist">
            {(["all", "active", "inactive"] as Filter[]).map((key) => <button
              aria-selected={filter === key}
              className={`filter-tab${filter === key ? " selected" : ""}`}
              key={key}
              onClick={() => setFilter(key)}
              role="tab"
              type="button"
            >{key === "all" ? "Todas" : key === "active" ? "Activas" : "Inactivas"}<span>{counts[key]}</span></button>)}
          </div>
          <span className="results-count">{visibleSubscriptions.length} {visibleSubscriptions.length === 1 ? "servicio" : "servicios"}</span>
        </div>
        {loading ? <LoadingState label="Cargando suscripciones…" /> : !error && visibleSubscriptions.length === 0 ? (
          subscriptions.length === 0 ?
            <EmptyState title="Empieza con tu primera suscripción" message="Agrega un servicio recurrente para llevar control de su precio y próxima fecha de cobro." action={{ label: "Crear suscripción", onClick: () => setFormSubscription(null) }} /> :
            <EmptyState title={`No hay suscripciones ${filter === "active" ? "activas" : "inactivas"}`} message="Prueba otro filtro para ver el resto de tus servicios." />
        ) : !error && (
          <div className="subscription-list">{visibleSubscriptions.map((subscription) => <SubscriptionRow
            key={subscription.subscription_id}
            subscription={subscription}
            busy={busyId === subscription.subscription_id}
            onEdit={() => setFormSubscription(subscription)}
      onToggle={() => void toggleActive(subscription)}
            onDelete={() => setDeleting(subscription)}
          />)}</div>
        )}
      </section>
      <div className="list-note"><span className="footnote-mark">i</span>Las suscripciones inactivas se conservan, pero no se incluyen en el gasto estimado ni en los avisos.</div>
      {formSubscription !== undefined && <SubscriptionFormModal subscription={formSubscription ?? undefined} onClose={() => setFormSubscription(undefined)} onSaved={saved} />}
      {deleting && <ConfirmDialog
        title="Eliminar suscripción"
        message={`Se eliminará ${deleting.name} junto con todo su historial de cobros. Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar definitivamente"
        destructive
        busy={busyId === deleting.subscription_id}
        onCancel={() => setDeleting(null)}
        onConfirm={() => void removeSubscription()}
      />}
    </>
  );
}

function SubscriptionRow({
  subscription,
  busy,
  onEdit,
  onToggle,
  onDelete,
}: {
  subscription: Subscription;
  busy: boolean;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="subscription-row">
      <Link className="service-avatar" to={`/suscripciones/${subscription.subscription_id}`} aria-label={`Ver detalle de ${subscription.name}`}>{subscription.name.trim().charAt(0).toUpperCase() || "S"}</Link>
      <div className="subscription-name"><Link to={`/suscripciones/${subscription.subscription_id}`}><strong>{subscription.name}</strong></Link><small>{subscription.billing_cycle === "monthly" ? "Mensual" : "Anual"} · Próximo cobro {formatDate(subscription.renewal_date)}</small></div>
      <div className="subscription-cost"><strong>{formatMoney(subscription.cost)}</strong><small>por {subscription.billing_cycle === "monthly" ? "mes" : "año"}</small></div>
      <span className={`status-badge ${subscription.is_active ? "badge-active" : "badge-inactive"}`}><span />{subscription.is_active ? "Activa" : "Inactiva"}</span>
      <div className="row-actions">
        <button aria-label={`Editar ${subscription.name}`} className="button button-quiet button-small" onClick={onEdit} type="button">Editar</button>
        <button className="button button-quiet button-small" disabled={busy} onClick={onToggle} type="button">{busy ? "…" : subscription.is_active ? "Desactivar" : "Reactivar"}</button>
        <button aria-label={`Eliminar ${subscription.name}`} className="icon-button row-delete" disabled={busy} onClick={onDelete} type="button"><span className="sr-only">Eliminar</span><Icon name="close" /></button>
      </div>
    </article>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { formatDate, formatMoney, renewalStatus } from "../format";
import type { RenewalAlert, Subscription, Summary } from "../types";

export function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [alerts, setAlerts] = useState<RenewalAlert[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextAlerts, nextSubscriptions] = await Promise.all([
        api.getSummary(), api.getAlerts(), api.listSubscriptions(),
      ]);
      setSummary(nextSummary);
      setAlerts(nextAlerts);
      setSubscriptions(nextSubscriptions);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo cargar el panel.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const overdue = alerts.filter((alert) => alert.days_until_renewal < 0);
  const upcoming = alerts.filter((alert) => alert.days_until_renewal >= 0);
  const subscriptionById = new Map(subscriptions.map((subscription) => [subscription.subscription_id, subscription]));

  return (
    <>
      <div className="page-heading dashboard-heading">
        <div><div className="eyebrow">TU PANORAMA</div><h1>Resumen</h1><p>Un vistazo claro a tus suscripciones y próximos cobros.</p></div>
        <Link className="button button-primary" to="/suscripciones"><Icon name="plus" />Administrar suscripciones</Link>
      </div>
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {loading ? <LoadingState label="Preparando tu resumen…" /> : !error && (
        <>
          <section aria-label="Gasto mensual estimado" className="summary-banner">
            <div className="summary-copy"><span className="summary-icon"><Icon name="overview" /></span><div><span>Gasto mensual estimado</span><small>Equivalente mensual de tus suscripciones activas</small></div></div>
            <strong className="summary-amount">{formatMoney(summary?.total_monthly_cost ?? "0")}</strong>
            <span className="summary-decoration" aria-hidden="true">S/</span>
          </section>

          <div className="dashboard-section-title"><div><div className="eyebrow">LO QUE VIENE</div><h2>Cobros pendientes</h2></div><Link className="text-link" to="/suscripciones">Ver todas <Icon name="arrow" /></Link></div>

          {alerts.length === 0 ? (
            <EmptyState title="Todo tranquilo por ahora" message="No tienes cobros vencidos ni próximos dentro de las ventanas de aviso." action={{ label: "Ver suscripciones", onClick: () => navigate("/suscripciones") }} />
          ) : (
            <div className="alert-columns">
              <section className="alert-section">
                <div className="section-heading"><div><span className="status-dot status-overdue" /><h3>Vencidos</h3></div><span className="count-pill count-danger">{overdue.length}</span></div>
                {overdue.length === 0 ? <p className="section-empty">No hay cobros vencidos.</p> : <div className="alert-list">{overdue.map((alert) => <AlertRow key={alert.subscription_id} alert={alert} cost={subscriptionById.get(alert.subscription_id)?.cost} />)}</div>}
              </section>
              <section className="alert-section">
                <div className="section-heading"><div><span className="status-dot status-upcoming" /><h3>Próximos</h3></div><span className="count-pill">{upcoming.length}</span></div>
                {upcoming.length === 0 ? <p className="section-empty">No hay cobros próximos dentro de la ventana de aviso.</p> : <div className="alert-list">{upcoming.map((alert) => <AlertRow key={alert.subscription_id} alert={alert} cost={subscriptionById.get(alert.subscription_id)?.cost} />)}</div>}
              </section>
            </div>
          )}

          <div className="dashboard-footnote"><span className="footnote-mark">i</span>El monto mensual es una estimación y no representa pagos realizados.</div>
        </>
      )}
    </>
  );
}

function AlertRow({ alert, cost }: { alert: RenewalAlert; cost?: string }) {
  const overdue = alert.days_until_renewal < 0;
  return (
    <Link className="alert-row" to={`/suscripciones/${alert.subscription_id}`}>
      <span className={`service-avatar${overdue ? " avatar-warm" : ""}`}>{alert.name.trim().charAt(0).toUpperCase() || "S"}</span>
      <span className="alert-main"><strong>{alert.name}</strong><small>{alert.billing_cycle === "monthly" ? "Mensual" : "Anual"} · {formatDate(alert.renewal_date)}</small></span>
      <span className="alert-tail"><strong className={overdue ? "text-danger" : ""}>{cost ? formatMoney(cost) : renewalStatus(alert)}</strong><small>{renewalStatus(alert)}</small></span>
      <Icon className="row-chevron" name="chevron" />
    </Link>
  );
}

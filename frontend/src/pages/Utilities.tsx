import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import type { Utility } from "../types";

export function Utilities() {
  const [utilities, setUtilities] = useState<Utility[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.listUtilities().then((result) => {
      if (active) setUtilities(result);
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof ApiError ? caught.message : "No se pudieron cargar los servicios.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [attempt]);

  return (
    <>
      <div className="page-heading">
        <div><h1>Servicios</h1><p>Luz, agua, internet y otros servicios de tu hogar. Aquí llevas el control de tu aporte personal.</p></div>
      </div>
      {loading ? <LoadingState label="Cargando servicios…" /> : error ? (
        <ErrorState message={error} onRetry={() => setAttempt((value) => value + 1)} />
      ) : utilities.length === 0 ? (
        <EmptyState title="Aún no tienes servicios registrados" message="Tus servicios aparecerán aquí cuando los registres." />
      ) : (
        <section className="list-panel" aria-label="Catálogo de servicios">
          <div className="list-toolbar utility-catalog-toolbar"><h2>Mis servicios</h2><span className="results-count">{utilities.length} {utilities.length === 1 ? "servicio" : "servicios"}</span></div>
          <ul className="utility-catalog">
            {utilities.map((utility) => (
              <li className="utility-catalog-row" key={utility.utility_id}>
                <span className="service-avatar" aria-hidden="true">{utility.name.charAt(0).toUpperCase()}</span>
                <div className="subscription-name"><strong>{utility.name}</strong>{utility.provider && <small>{utility.provider}</small>}</div>
                <span className={`status-badge ${utility.is_active ? "badge-active" : "badge-inactive"}`}><span />{utility.is_active ? "Activo" : "Archivado"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

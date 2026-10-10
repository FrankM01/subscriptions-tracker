import { Icon } from "./Icon";

export function LoadingState({ label = "Cargando información…" }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="spinner" />{label}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <span className="error-mark">!</span>
      <div><strong>No pudimos cargar esta información</strong><p>{message}</p></div>
      {onRetry && <button className="button button-quiet button-small" onClick={onRetry} type="button">Reintentar</button>}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon name="subscriptions" /></div>
      <h3>{title}</h3>
      <p>{message}</p>
      {action && <button className="button button-primary" onClick={action.onClick} type="button"><Icon name="plus" />{action.label}</button>}
    </div>
  );
}

import { useEffect, type ReactNode } from "react";
import { Icon } from "./Icon";

interface ModalProps {
  title: string;
  eyebrow?: string;
  onClose: () => void;
  children: ReactNode;
  size?: "normal" | "compact";
}

export function Modal({ title, eyebrow, onClose, children, size = "normal" }: ModalProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section
        aria-labelledby="modal-title"
        aria-modal="true"
        className={`modal-panel${size === "compact" ? " modal-compact" : ""}`}
        role="dialog"
      >
        <div className="modal-heading">
          <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2 id="modal-title">{title}</h2></div>
          <button aria-label="Cerrar" className="icon-button" onClick={onClose} type="button"><Icon name="close" /></button>
        </div>
        {children}
      </section>
    </div>
  );
}

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  busy?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  busy = false,
  destructive = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Modal title={title} eyebrow="CONFIRMA ESTA ACCIÓN" onClose={onCancel} size="compact">
      <p className="dialog-message">{message}</p>
      <div className="form-actions">
        <button className="button button-quiet" onClick={onCancel} type="button">Cancelar</button>
        <button
          className={`button ${destructive ? "button-danger" : "button-primary"}`}
          disabled={busy}
          onClick={onConfirm}
          type="button"
        >{busy ? "Procesando…" : confirmLabel}</button>
      </div>
    </Modal>
  );
}

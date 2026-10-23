/**
 * Accessible confirmation dialog for destructive actions (resign, reset).
 * Closes on Escape and overlay click; focuses the confirm button on open.
 */
import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

type Props = {
  title: string;
  description: ReactNode;
  confirmLabel: string;
  confirmTone?: 'primary' | 'danger';
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  title,
  description,
  confirmLabel,
  confirmTone = 'primary',
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="modal-title">{title}</p>
        <p className="modal-desc">{description}</p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            ref={confirmRef}
            className={`btn ${confirmTone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

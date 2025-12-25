// src/components/common/Modal.tsx
import { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  children: ReactNode;
  maxWidth?: string;
}

export function Modal({
  open,
  title,
  onClose,
  onConfirm,
  confirmText = "確認",
  children,
  maxWidth,
}: ModalProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={maxWidth ? { maxWidth } : undefined}>
        {title && <h3 className="modal-title">{title}</h3>}
        <div className="modal-body">{children}</div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            取消
          </button>
          {onConfirm && (
            <button className="btn-primary" onClick={onConfirm}>
              {confirmText}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

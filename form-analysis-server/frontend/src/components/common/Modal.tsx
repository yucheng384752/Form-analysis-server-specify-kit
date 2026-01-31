// src/components/common/Modal.tsx
import { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface ModalProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  cancelText?: string;
  hideFooter?: boolean;
  children: ReactNode;
  maxWidth?: string;
}

export function Modal({
  open,
  title,
  onClose,
  onConfirm,
  confirmText,
  cancelText,
  hideFooter = false,
  children,
  maxWidth,
}: ModalProps) {
  const { t } = useTranslation();
  const resolvedCancelText = cancelText ?? t("common.cancel");
  const resolvedConfirmText = confirmText ?? t("common.ok");

  if (!open) return null;
  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={maxWidth ? { maxWidth } : undefined}>
        {title && <h3 className="modal-title">{title}</h3>}
        <div className="modal-body">{children}</div>
        {!hideFooter && (
          <div className="modal-footer">
            <button className="btn-secondary" onClick={onClose}>
              {resolvedCancelText}
            </button>
            {onConfirm && (
              <button className="btn-primary" onClick={onConfirm}>
                {resolvedConfirmText}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

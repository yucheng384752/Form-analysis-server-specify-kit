// src/components/common/ToastContainer.tsx
import { useToast } from "./ToastContext";

export function ToastContainer() {
  const { toasts, removeToast } = useToast();
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast toast--${t.type}`}
          onClick={() => removeToast(t.id)}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

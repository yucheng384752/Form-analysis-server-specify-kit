// src/components/common/ToastContext.tsx
import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
} from "react";

export type ToastType = "info" | "error" | "success";

export interface Toast {
  id: number;
  type: ToastType;
  message: string;
  key?: string;
}

export interface ShowToastOptions {
  key?: string;
  durationMs?: number | null;
}

interface ToastContextValue {
  toasts: Toast[];
  showToast: (type: ToastType, message: string, options?: ShowToastOptions) => void;
  removeToast: (id: number) => void;
  clearToasts: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  const showToast = useCallback(
    (type: ToastType, message: string, options?: ShowToastOptions) => {
      const id = Date.now() * 1000 + (counterRef.current++ % 1000);
      const key = typeof options?.key === 'string' && options.key ? options.key : undefined;
      const durationMs = options?.durationMs ?? 1500;

      setToasts((prev) => {
        const filtered = key ? prev.filter((t) => t.key !== key) : prev;
        const toast = key ? ({ id, type, message, key } as Toast) : ({ id, type, message } as Toast);
        return [...filtered, toast];
      });

      if (durationMs !== null) {
        setTimeout(() => removeToast(id), durationMs);
      }
    },
    [removeToast]
  );

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent)?.detail as { type?: ToastType; message?: string } | undefined
      const message = typeof detail?.message === 'string' ? detail.message : ''
      if (!message) return
      const type: ToastType = detail?.type === 'success' || detail?.type === 'error' || detail?.type === 'info' ? detail.type : 'info'
      showToast(type, message)
    }

    window.addEventListener('app:toast', handler as EventListener)
    return () => window.removeEventListener('app:toast', handler as EventListener)
  }, [showToast])

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast, clearToasts }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

import { useEffect, useState } from 'react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

interface ToastProps {
  message: ToastMessage;
  onClose: (id: string) => void;
}

const Toast: React.FC<ToastProps> = ({ message, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose(message.id);
    }, message.duration || 5000);

    return () => clearTimeout(timer);
  }, [message.id, message.duration, onClose]);

  return (
    <div className={`figma-toast figma-toast-${message.type}`}>
      <div className="figma-toast-header">
        <h4 style={{ margin: 0, fontWeight: 600 }}>{message.title}</h4>
        <button 
          onClick={() => onClose(message.id)}
          style={{ 
            background: 'none', 
            border: 'none', 
            cursor: 'pointer',
            fontSize: '1.2rem',
            color: 'var(--gray-500)'
          }}
        >
          ×
        </button>
      </div>
      {message.message && (
        <p style={{ margin: '0.5rem 0 0 0', color: 'var(--gray-600)' }}>
          {message.message}
        </p>
      )}
    </div>
  );
};

// Toast Container Hook
export const useToast = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (toast: Omit<ToastMessage, 'id'>) => {
    const id = Math.random().toString(36).substring(7);
    setToasts(prev => [...prev, { ...toast, id }]);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const ToastContainer = () => (
    <div style={{ 
      position: 'fixed', 
      top: '1rem', 
      right: '1rem', 
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem'
    }}>
      {toasts.map(toast => (
        <Toast key={toast.id} message={toast} onClose={removeToast} />
      ))}
    </div>
  );

  return { addToast, ToastContainer };
};
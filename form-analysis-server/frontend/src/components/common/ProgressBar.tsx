// src/components/common/ProgressBar.tsx
interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
}

export function ProgressBar({ value, label }: ProgressBarProps) {
  return (
    <div className="progress">
      {label && <div className="progress-label">{label}</div>}
      <div className="progress-track">
        <div
          className="progress-value"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}

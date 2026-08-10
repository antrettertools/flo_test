import type { ReactNode } from 'react';

type AlertType = 'success' | 'warning' | 'error' | 'info';

const STYLES: Record<AlertType, { bg: string; border: string; text: string; icon: string }> = {
  success: { bg: 'bg-c3-greenlight/10', border: 'border-c3-greenlight', text: 'text-c3-greenlight', icon: '✓' },
  warning: { bg: 'bg-c3-orange/10', border: 'border-c3-orange', text: 'text-c3-orange', icon: '⚠' },
  error: { bg: 'bg-c3-red/10', border: 'border-c3-red', text: 'text-c3-red', icon: '✕' },
  info: { bg: 'bg-c3-blue/10', border: 'border-c3-blue', text: 'text-c3-blue', icon: 'ℹ' },
};

interface AlertProps {
  type?: AlertType;
  title?: string;
  onClose?: () => void;
  children: ReactNode;
}

export function Alert({ type = 'info', title, onClose, children }: AlertProps) {
  const style = STYLES[type];
  return (
    <div className={`rounded-lg border-l-4 p-4 ${style.bg} ${style.border}`}>
      <div className="flex">
        <span className={`text-lg ${style.text}`}>{style.icon}</span>
        <div className="ml-3 flex-1">
          {title && <h3 className={`text-sm font-medium ${style.text}`}>{title}</h3>}
          <div className={`text-sm ${style.text} ${title ? 'mt-2' : ''}`}>{children}</div>
        </div>
        {onClose && (
          <button onClick={onClose} className={`ml-auto text-sm ${style.text} hover:opacity-75`}>
            {'✕'}
          </button>
        )}
      </div>
    </div>
  );
}

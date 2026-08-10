import type { ReactNode } from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  className?: string;
  children: ReactNode;
}

export function Card({ title, subtitle, className = '', children }: CardProps) {
  return (
    <div className={`bg-white rounded-xl shadow-md border border-c3-greylight ${className}`}>
      {(title || subtitle) && (
        <div className="px-6 py-4 border-b border-c3-greylight">
          {title && <h3 className="text-lg font-semibold text-c3-text">{title}</h3>}
          {subtitle && <p className="text-sm text-c3-greydark mt-1">{subtitle}</p>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}

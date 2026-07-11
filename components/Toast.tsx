'use client';

import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

export function Toast({
  message,
  onClose,
  variant = 'error',
  title,
}: {
  message: string;
  onClose: () => void;
  variant?: 'error' | 'success';
  title?: string;
}) {
  const isSuccess = variant === 'success';
  const Icon = isSuccess ? CheckCircle2 : AlertTriangle;
  const accent = isSuccess ? 'border-success' : 'border-error';
  const iconColor = isSuccess ? 'text-success' : 'text-error';
  const label = title ?? (isSuccess ? 'Success' : 'Ingestion error');
  return (
    <div
      className="fixed bottom-6 right-6 z-50 max-w-sm bg-inverse rounded-sm anim-fade-up"
      style={{ boxShadow: 'var(--shadow-3)' }}
      data-testid={isSuccess ? 'success-toast' : 'error-toast'}
      role={isSuccess ? 'status' : 'alert'}
    >
      <div className={['flex items-start gap-3 px-4 py-3 border-l-2', accent].join(' ')}>
        <Icon className={['h-4 w-4 shrink-0 mt-0.5', iconColor].join(' ')} strokeWidth={2} />
        <div className="min-w-0">
          <div className={['font-mono text-[10px] tracking-meta uppercase mb-0.5', iconColor].join(' ')}>{label}</div>
          <p className="font-mono text-[12px] text-fg-inverse leading-snug">{message}</p>
        </div>
        <button onClick={onClose} className="text-fg-inverse/60 hover:text-fg-inverse shrink-0" aria-label="Dismiss">
          <X className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}

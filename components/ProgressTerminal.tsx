'use client';

import { Check, Loader2 } from 'lucide-react';

export function ProgressTerminal({
  scheme,
  steps,
  current,
}: {
  scheme: string;
  steps: string[];
  current: number;
}) {
  return (
    <div className="max-w-2xl mx-auto bg-card border border-line-subtle rounded-sm overflow-hidden" data-testid="progress-terminal">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-subtle border-b border-line-subtle">
        <span className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-muted" />
          <span className="h-2.5 w-2.5 rounded-full bg-muted" />
          <span className="h-2.5 w-2.5 rounded-full bg-muted" />
        </span>
        <span className="font-mono text-[11px] text-fg-secondary truncate">
          analyse://{scheme}
        </span>
      </div>
      <div className="px-4 py-4 font-mono text-[12.5px] leading-relaxed space-y-1.5">
        {steps.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div
              key={i}
              className={[
                'flex items-center gap-2',
                done ? 'text-fg-default' : active ? 'text-fg-primary' : 'text-fg-disabled',
              ].join(' ')}
            >
              {done ? (
                <Check className="h-3.5 w-3.5 text-success shrink-0" strokeWidth={2.5} />
              ) : active ? (
                <Loader2 className="h-3.5 w-3.5 text-primary shrink-0 anim-spin" strokeWidth={2.5} />
              ) : (
                <span className="h-3.5 w-3.5 shrink-0 flex items-center justify-center text-fg-disabled">›</span>
              )}
              <span>{s}</span>
              {active && <span className="cursor-blink text-primary">▋</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

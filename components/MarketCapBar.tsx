'use client';

import { catColor } from '@/lib/ui';
import type { WeightItem } from '@/lib/types';

export function MarketCapBar({ data }: { data: WeightItem[] }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.weight), 1);
  return (
    <div className="bg-card border border-line-subtle rounded-sm p-4" data-testid="market-cap-bar">
      <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary mb-3">Market Cap Split</h3>
      <div className="space-y-3">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center gap-3">
            <span className="w-14 shrink-0 font-mono text-[11px] text-fg-default">{d.name.replace(' Cap', '')}</span>
            <div className="flex-1 h-2.5 bg-muted rounded-sm overflow-hidden">
              <div
                className="h-full rounded-sm"
                style={{ width: `${(d.weight / max) * 100}%`, background: catColor(i) }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-[12px] text-fg-primary tabular-nums">
              {d.weight.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
      <p className="font-mono text-[10px] text-fg-disabled mt-3 leading-snug">% of total portfolio · equity sleeve only</p>
    </div>
  );
}

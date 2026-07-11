'use client';

import { catColor } from '@/lib/ui';
import type { WeightItem } from '@/lib/types';

export function AssetAllocationBar({ data }: { data: WeightItem[] }) {
  const total = data.reduce((a, b) => a + b.weight, 0) || 100;
  return (
    <div className="bg-card border border-line-subtle rounded-sm p-4" data-testid="asset-allocation-bar">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary">Asset Allocation</h3>
        <span className="font-mono text-[11px] text-fg-disabled tabular-nums">{total.toFixed(0)}% total</span>
      </div>
      <p className="text-[11px] text-fg-secondary leading-snug mb-3">
        How the fund&apos;s money is split across broad asset types — equity, debt, cash, etc.
      </p>
      <div className="flex h-9 w-full rounded-sm overflow-hidden border border-line-subtle">
        {data.map((d, i) => {
          const color = catColor(i, d.name);
          const pct = (d.weight / total) * 100;
          return (
            <div
              key={d.name}
              className="flex items-center justify-center min-w-0"
              style={{ width: `${pct}%`, background: color }}
              title={`${d.name}: ${d.weight.toFixed(2)}%`}
            >
              {pct > 9 && (
                <span className="font-mono text-[11px] font-medium text-white/95 truncate px-1 tabular-nums">
                  {d.weight.toFixed(1)}%
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: catColor(i, d.name) }} />
            <span className="text-[12px] text-fg-default">{d.name}</span>
            <span className="font-mono text-[12px] text-fg-secondary tabular-nums">{d.weight.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

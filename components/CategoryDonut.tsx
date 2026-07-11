'use client';

import { useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { catColor } from '@/lib/ui';
import type { WeightItem } from '@/lib/types';

// Hovering a slice writes its value into the centre of the ring (no floating
// tooltip to collide with the centre label) and highlights its legend row.
export function CategoryDonut({
  data,
  title,
  centerLabel,
}: {
  data: WeightItem[];
  title: string;
  centerLabel: string;
}) {
  const sorted = [...data].sort((a, b) => b.weight - a.weight);
  const total = sorted.reduce((a, b) => a + b.weight, 0);
  const [active, setActive] = useState<number | null>(null);
  const sel = active != null ? sorted[active] : null;

  return (
    <div className="bg-card border border-line-subtle rounded-sm p-4 h-full" data-testid="category-donut">
      <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary mb-3">{title}</h3>
      <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-5">
        <div className="relative h-[160px] w-[160px] sm:h-[176px] sm:w-[176px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={sorted}
                dataKey="weight"
                nameKey="name"
                innerRadius={58}
                outerRadius={84}
                paddingAngle={1}
                stroke="var(--surface-card)"
                strokeWidth={2}
                startAngle={90}
                endAngle={-270}
                onMouseLeave={() => setActive(null)}
              >
                {sorted.map((d, i) => (
                  <Cell
                    key={d.name}
                    fill={catColor(i, d.name)}
                    opacity={active == null || active === i ? 1 : 0.32}
                    style={{ transition: 'opacity 120ms', cursor: 'pointer' }}
                    onMouseEnter={() => setActive(i)}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-6 text-center">
            <span className="font-mono text-[22px] font-medium text-fg-primary leading-none tabular-nums">
              {sel ? `${sel.weight.toFixed(2)}%` : sorted.length}
            </span>
            <span className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary mt-1 leading-tight line-clamp-2">
              {sel ? sel.name : centerLabel}
            </span>
          </div>
        </div>
        <ul className="flex-1 w-full grid grid-cols-1 gap-y-0.5 min-w-0">
          {sorted.map((d, i) => {
            const on = active === i;
            return (
              <li
                key={d.name}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                className={[
                  'flex items-center gap-2.5 rounded-sm px-1.5 py-1 -mx-1.5 cursor-default transition-colors',
                  on ? 'bg-subtle' : '',
                  active != null && !on ? 'opacity-40' : '',
                ].join(' ')}
              >
                <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: catColor(i, d.name) }} />
                <span className={['text-[12.5px] flex-1 truncate', on ? 'text-fg-primary' : 'text-fg-default'].join(' ')}>
                  {d.name}
                </span>
                <span className="font-mono text-[12px] text-fg-primary tabular-nums">{d.weight.toFixed(2)}%</span>
              </li>
            );
          })}
          <li className="flex items-center gap-2.5 px-1.5 pt-1.5 mt-1 -mx-1.5 border-t border-line-subtle">
            <span className="h-2.5 w-2.5 shrink-0" />
            <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary flex-1">Disclosed</span>
            <span className="font-mono text-[12px] text-fg-secondary tabular-nums">{total.toFixed(2)}%</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

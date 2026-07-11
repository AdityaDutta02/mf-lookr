'use client';

import { useMemo, useState } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { InstrumentTag } from '@/components/InstrumentTag';
import { parseHoldingName } from '@/lib/ui';
import type { Holding } from '@/lib/types';

type SortKey = 'name' | 'isin' | 'instrument_type' | 'sector' | 'quantity' | 'market_value' | 'weight';
type Dir = 'asc' | 'desc';

// Base holdings table (not the changes/deltas panel) — quantity and ₹ market
// value are both legitimate here, unlike ChangesPanel where only quantity
// deltas are allowed. See ChangesPanel.tsx for that restriction.
const COLS: { key: SortKey; label: string; num?: boolean; mono?: boolean; align?: 'right'; tooltip?: string }[] = [
  { key: 'name', label: 'Holding' },
  { key: 'isin', label: 'ISIN', mono: true },
  { key: 'instrument_type', label: 'Type' },
  { key: 'sector', label: 'Sector' },
  {
    key: 'quantity',
    label: 'Quantity',
    num: true,
    mono: true,
    align: 'right',
    tooltip: 'Number of shares/units the fund holds — 0 or blank means the source disclosure didn’t report a count.',
  },
  {
    key: 'market_value',
    label: 'Mkt Val ₹cr',
    num: true,
    mono: true,
    align: 'right',
    tooltip: 'The rupee value of this holding, in crores, as of the disclosure date.',
  },
  {
    key: 'weight',
    label: 'Weight %',
    num: true,
    mono: true,
    align: 'right',
    tooltip: 'What % of the fund’s total assets this single holding makes up.',
  },
];

export function HoldingsTable({ data }: { data: Holding[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('weight');
  const [dir, setDir] = useState<Dir>('desc');

  const rows = useMemo(() => {
    const out = [...data];
    out.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      let cmp: number;
      if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv));
      return dir === 'asc' ? cmp : -cmp;
    });
    return out;
  }, [data, sortKey, dir]);

  function toggle(k: SortKey) {
    if (k === sortKey) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(k);
      setDir(k === 'name' || k === 'isin' || k === 'instrument_type' || k === 'sector' ? 'asc' : 'desc');
    }
  }

  const maxW = Math.max(...data.map((d) => d.weight), 1);

  // Beyond ~12 rows the table grows past a screen; cap it and scroll internally
  // so the page below (and the table's own footer) stays anchored.
  const SCROLL_AFTER = 12;
  const scrolls = data.length > SCROLL_AFTER;

  return (
    <div className="bg-card border border-line-subtle rounded-sm" data-testid="holdings-table">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line-subtle">
        <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary">All Holdings</h3>
        <span className="font-mono text-[10px] text-fg-disabled">
          {scrolls ? `${data.length} rows · scroll · click a column to sort` : 'click a column to sort'}
        </span>
      </div>
      <div className={['overflow-x-auto overflow-y-auto scroll-thin', scrolls ? 'max-h-[520px]' : ''].join(' ')}>
        <table className="w-full border-collapse min-w-[760px]">
          <thead className="sticky top-0 z-10">
            <tr className="bg-subtle shadow-[inset_0_-1px_0_var(--border-subtle)]">
              <th className="w-9 px-3 py-2 text-left font-mono text-[10px] tracking-meta uppercase text-fg-disabled">#</th>
              {COLS.map((c) => {
                const active = c.key === sortKey;
                const Icon = active ? (dir === 'asc' ? ChevronUp : ChevronDown) : ChevronsUpDown;
                return (
                  <th
                    key={c.key}
                    className={['px-3 py-2 font-mono text-[10px] tracking-meta uppercase', c.align === 'right' ? 'text-right' : 'text-left'].join(' ')}
                  >
                    <button
                      onClick={() => toggle(c.key)}
                      className={[
                        'inline-flex items-center gap-1 hover:text-fg-primary transition-colors focus-ring rounded-sm',
                        active ? 'text-primary-hover' : 'text-fg-secondary',
                        c.align === 'right' ? 'flex-row-reverse' : '',
                        c.tooltip ? 'cursor-help' : '',
                      ].join(' ')}
                      data-testid={`sort-${c.key}`}
                      title={c.tooltip}
                    >
                      {c.label}
                      <Icon className="h-3 w-3" strokeWidth={2.25} />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((h, i) => {
              const { displayName, maturityDate } = parseHoldingName(h.name);
              return (
              <tr key={h.isin + i} className="border-b border-line-subtle last:border-0 hover:bg-subtle transition-colors">
                <td className="px-3 py-2 font-mono text-[11px] text-fg-disabled tabular-nums">{i + 1}</td>
                <td className="px-3 py-2 text-[12.5px] text-fg-primary">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="truncate">{displayName}</span>
                    <InstrumentTag type={h.instrument_type} />
                    {maturityDate && (
                      <span className="font-mono text-[9px] text-fg-disabled shrink-0" title={`Matures ${maturityDate}`}>
                        {maturityDate}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 font-mono text-[11.5px] text-fg-secondary tabular-nums">{h.isin}</td>
                <td className="px-3 py-2 text-[12px] text-fg-default whitespace-nowrap">{h.instrument_type}</td>
                <td className="px-3 py-2 text-[12px] text-fg-secondary whitespace-nowrap">{h.sector}</td>
                <td className="px-3 py-2 text-right font-mono text-[12px] text-fg-secondary tabular-nums">
                  {h.quantity ? Math.round(h.quantity).toLocaleString('en-IN') : '—'}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[12px] text-fg-default tabular-nums">
                  {h.market_value > 0 ? h.market_value.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '—'}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-2">
                    <span className="block h-1 w-12 bg-muted rounded-sm overflow-hidden">
                      <span className="block h-full bg-primary rounded-sm" style={{ width: `${(h.weight / maxW) * 100}%` }} />
                    </span>
                    <span className="font-mono text-[12.5px] text-fg-primary tabular-nums w-12 text-right">
                      {h.weight.toFixed(2)}
                    </span>
                  </div>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

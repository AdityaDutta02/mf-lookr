'use client';

import { useMemo } from 'react';
import { InstrumentTag } from '@/components/InstrumentTag';
import { parseHoldingName } from '@/lib/ui';
import type { Holding, TopHolding } from '@/lib/types';

// top_holdings (unlike the full `holdings` list) doesn't carry instrument_type
// at the data layer — look it up by ISIN/name from the already-fetched full
// holdings list (same AnalyseData payload, no extra API call) so top-10 rows
// can still be tagged CD/CP/etc. See task brief bug 3.
export function TopHoldings({
  data,
  totalCount,
  holdings,
}: {
  data: TopHolding[];
  totalCount: number;
  holdings?: Holding[];
}) {
  const typeByKey = useMemo(() => {
    const m = new Map<string, string>();
    for (const h of holdings ?? []) {
      if (h.isin && h.isin !== '—') m.set(h.isin, h.instrument_type);
      m.set(h.name, h.instrument_type);
    }
    return m;
  }, [holdings]);
  const typeFor = (h: TopHolding) => (h.isin && h.isin !== '—' ? typeByKey.get(h.isin) : undefined) ?? typeByKey.get(h.name);
  const max = Math.max(...data.map((d) => d.weight), 1);
  const top10Sum = data.reduce((a, b) => a + b.weight, 0);
  return (
    <div className="bg-card border border-line-subtle rounded-sm p-4 h-full" data-testid="top-holdings">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary">Top 10 Holdings</h3>
        <span className="font-mono text-[11px] text-fg-disabled tabular-nums">of {totalCount}</span>
      </div>
      <p className="font-mono text-[11px] text-fg-secondary mb-3 tabular-nums">
        {top10Sum.toFixed(1)}% of portfolio
      </p>
      <ol>
        {data.map((h, i) => {
          const { displayName, maturityDate } = parseHoldingName(h.name);
          return (
          <li
            key={h.isin + i}
            className="relative flex items-center gap-3 py-2 border-b border-line-subtle last:border-0"
          >
            <span className="w-5 shrink-0 font-mono text-[12px] text-fg-disabled tabular-nums text-right">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-[13px] text-fg-primary truncate leading-tight">{displayName}</span>
                <InstrumentTag type={typeFor(h)} />
                {maturityDate && (
                  <span className="font-mono text-[9px] text-fg-disabled shrink-0" title={`Matures ${maturityDate}`}>
                    {maturityDate}
                  </span>
                )}
              </div>
              <div className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary truncate mt-0.5">
                {h.sector}
              </div>
            </div>
            <div className="shrink-0 flex flex-col items-end gap-1">
              <span className="font-mono text-[13px] text-fg-primary tabular-nums leading-none">
                {h.weight.toFixed(2)}%
              </span>
              <span className="block h-1 w-16 bg-muted rounded-sm overflow-hidden">
                <span className="block h-full bg-primary rounded-sm" style={{ width: `${(h.weight / max) * 100}%` }} />
              </span>
            </div>
          </li>
          );
        })}
      </ol>
    </div>
  );
}

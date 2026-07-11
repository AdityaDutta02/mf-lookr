'use client';

// Rebuilt, not ported verbatim — see task brief: the old app's ChangesPanel
// bucketed by weight/NAV delta, which conflates manager activity with pure
// price drift (a position can be untouched while its weight moves >0.4%
// just because the stock re-rated). This version keeps the old panel's
// visual shell/card style but buckets and displays ONLY share-quantity
// deltas — display logic ported 1:1 from app/page.tsx's ChangeList
// function, which was already correct. Never render weight-of-NAV or
// ₹-value deltas for individual holdings here.
import { useState } from 'react';
import { Info, Plus, Minus, TrendingUp, TrendingDown } from 'lucide-react';
import { InstrumentTag } from '@/components/InstrumentTag';
import { parseHoldingName } from '@/lib/ui';
import type { ChangeRow, ChangesData } from '@/lib/types';

function fmtSigned(n: number, suffix = '%') {
  const s = n > 0 ? '+' : '';
  return `${s}${n.toFixed(2)}${suffix}`;
}

function deltaColor(n: number) {
  return n > 0 ? 'text-success' : n < 0 ? 'text-error' : 'text-fg-secondary';
}

const BUCKET_TOOLTIP: Record<'added' | 'exited' | 'increased' | 'reduced', string> = {
  added: 'New = first time this fund is disclosed as holding this position.',
  increased: 'Increased = the fund bought more shares/units this month.',
  reduced: 'Reduced = the fund sold some shares/units, but the position is still open.',
  exited: 'Exited = the fund sold its entire position — no shares/units remain.',
};

const ROWS_COLLAPSED = 8;

// Per-goal directive: quantity change only — never weight/NAV-value delta,
// which reflects price movement rather than an actual position change.
function ChangeRowList({ rows, kind }: { rows: ChangeRow[]; kind: 'added' | 'exited' | 'increased' | 'reduced' }) {
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0) return null;
  const label = { added: 'New', exited: 'Exited', increased: 'Increased', reduced: 'Reduced' }[kind];
  const Icon = kind === 'added' ? Plus : kind === 'exited' ? Minus : kind === 'increased' ? TrendingUp : TrendingDown;
  const iconTone = kind === 'exited' || kind === 'reduced' ? 'text-error' : 'text-success';
  const visible = rows.slice(0, expanded ? rows.length : ROWS_COLLAPSED);
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className={['h-3 w-3', iconTone].join(' ')} strokeWidth={2.25} />
        <span
          className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary cursor-help"
          title={BUCKET_TOOLTIP[kind]}
        >
          {label} ({rows.length})
        </span>
      </div>
      <ul className="space-y-1">
        {visible.map((r) => {
          const { displayName, maturityDate } = parseHoldingName(r.name);
          return (
            <li key={r.isin || r.name} className="flex items-center justify-between gap-2 text-[12.5px]">
              <span className="flex items-center gap-1.5 min-w-0">
                <span className="text-fg-default truncate">{displayName}</span>
                <InstrumentTag type={r.instrument_type} />
                {maturityDate && (
                  <span className="font-mono text-[9px] text-fg-disabled shrink-0" title={`Matures ${maturityDate}`}>
                    {maturityDate}
                  </span>
                )}
              </span>
              {r.quantity_delta != null ? (
                <span
                  className={['font-mono tabular-nums shrink-0', deltaColor(r.quantity_delta)].join(' ')}
                  title={`${Math.round(r.quantity_delta).toLocaleString('en-IN')} units`}
                >
                  {r.quantity_delta >= 0 ? '+' : ''}
                  {r.quantity_delta_pct != null ? fmtSigned(r.quantity_delta_pct) : Math.round(r.quantity_delta).toLocaleString('en-IN')}
                </span>
              ) : (
                <span className="text-[11px] text-fg-secondary font-mono shrink-0">qty not disclosed</span>
              )}
            </li>
          );
        })}
      </ul>
      {rows.length > ROWS_COLLAPSED && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-1 text-[11px] text-fg-secondary font-mono hover:text-fg-primary transition-colors focus-ring rounded-sm"
          data-testid={`changes-expand-${kind}`}
        >
          {expanded ? 'Show less' : `+${rows.length - ROWS_COLLAPSED} more`}
        </button>
      )}
    </div>
  );
}

export function ChangesPanel({ data, fromLabel, toLabel }: { data: ChangesData; fromLabel: string; toLabel: string }) {
  const { kpis, changes, category_drift } = data;
  if (!kpis || !changes) return <ChangesUnavailable message="No prior month stored yet for this fund." />;

  const hasAnyChanges =
    changes.added.length + changes.exited.length + changes.increased.length + changes.reduced.length > 0;

  return (
    <section className="bg-card border border-line-default rounded-sm h-full flex flex-col" data-testid="changes-panel">
      <div className="flex items-center gap-2.5 px-3 h-9 border-b border-line-subtle shrink-0">
        <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">
          Changes <span className="text-fg-disabled">{fromLabel} → {toLabel}</span>
        </span>
      </div>

      <div className="p-3 space-y-4 overflow-y-auto scroll-thin" style={{ maxHeight: '420px' }}>
        <p className="text-[11px] text-fg-secondary leading-snug">
          Only real buy/sell activity is shown — moves driven purely by price, not by the fund manager, are excluded.
        </p>

        {/* Portfolio-level KPI deltas (aggregate cash/equity/count/AUM — not
            individual-holding deltas, so the quantity-only restriction below
            doesn't apply to this strip). */}
        <div className="grid grid-cols-2 gap-2">
          <div className="border border-line-subtle rounded-sm px-2.5 py-2">
            <div className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">Cash</div>
            <div className={['font-mono text-[13px] tabular-nums', deltaColor(kpis.cash_delta)].join(' ')}>
              {fmtSigned(kpis.cash_delta)}
            </div>
          </div>
          <div className="border border-line-subtle rounded-sm px-2.5 py-2">
            <div className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">Equity</div>
            <div className={['font-mono text-[13px] tabular-nums', deltaColor(kpis.equity_delta)].join(' ')}>
              {fmtSigned(kpis.equity_delta)}
            </div>
          </div>
          <div className="border border-line-subtle rounded-sm px-2.5 py-2">
            <div className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">Holdings</div>
            <div className={['font-mono text-[13px] tabular-nums', deltaColor(kpis.count_delta)].join(' ')}>
              {kpis.count_delta > 0 ? '+' : ''}
              {kpis.count_delta}
            </div>
          </div>
          <div className="border border-line-subtle rounded-sm px-2.5 py-2">
            <div className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">AUM (₹Cr)</div>
            <div className={['font-mono text-[13px] tabular-nums', kpis.aum_delta == null ? 'text-fg-secondary' : deltaColor(kpis.aum_delta)].join(' ')}>
              {kpis.aum_delta == null ? '—' : fmtSigned(kpis.aum_delta, '')}
            </div>
          </div>
        </div>

        {category_drift && category_drift.length > 0 && (
          <div>
            <div className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary mb-1">Category Drift</div>
            <p className="text-[11px] text-fg-secondary leading-snug mb-1.5">
              How the fund&apos;s mix across categories shifted this month.
            </p>
            <ul className="space-y-1">
              {category_drift.slice(0, 6).map((c) => (
                <li key={c.name} className="flex items-center justify-between gap-2 text-[12.5px]">
                  <span className="text-fg-default truncate">{c.name}</span>
                  <span className={['font-mono tabular-nums shrink-0', deltaColor(c.weight)].join(' ')}>{fmtSigned(c.weight)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {hasAnyChanges ? (
          <div className="space-y-4">
            <ChangeRowList rows={changes.added} kind="added" />
            <ChangeRowList rows={changes.increased} kind="increased" />
            <ChangeRowList rows={changes.reduced} kind="reduced" />
            <ChangeRowList rows={changes.exited} kind="exited" />
          </div>
        ) : (
          <div className="text-[12px] text-fg-secondary py-4 text-center">No holding-level changes detected.</div>
        )}
      </div>
    </section>
  );
}

export function ChangesUnavailable({ message }: { message: string }) {
  return (
    <section className="bg-card border border-line-subtle rounded-sm h-full flex flex-col items-center justify-center px-4 py-8 text-center gap-2" data-testid="changes-unavailable">
      <Info className="h-4 w-4 text-fg-disabled" strokeWidth={2} />
      <p className="text-[12.5px] text-fg-secondary max-w-xs">{message}</p>
    </section>
  );
}

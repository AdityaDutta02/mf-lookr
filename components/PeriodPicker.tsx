'use client';

// Ported near-verbatim from mf-analyser/components/PeriodPicker.tsx (presentational) —
// adapted to fetch from this app's /api/periods?fund=<amfi_code> (x-embed-token header,
// not the old app's lib/client fetchPeriods helper) and to the {period,year,month}[]
// shape /api/periods already returns (no PeriodOption.label/status here — this app
// doesn't have "fetchable"/"upload" states, only stored disclosures, so the label is
// derived from the period string and every listed period is implicitly "saved").
import { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, ChevronDown, ChevronLeft, Check } from 'lucide-react';
import type { FundSummary } from '@/lib/types';

interface PeriodRow {
  period: string;
  year: number;
  month: number;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function labelFor(p: PeriodRow) {
  return `${MONTHS[p.month - 1] ?? '?'} ${p.year}`;
}

export function PeriodPicker({
  fund,
  period,
  onSelect,
  token,
}: {
  fund: FundSummary | null;
  period: string | null;
  onSelect: (p: string) => void;
  token: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [periods, setPeriods] = useState<PeriodRow[]>([]);
  // Some funds now carry 100+ months of history (full-history backfills) — a
  // single flat scrolling list is unusable at that depth. Drill year -> month
  // instead: pick a year first, then the month within it.
  const [pickerYear, setPickerYear] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const years = useMemo(() => {
    const byYear = new Map<number, PeriodRow[]>();
    for (const p of periods) {
      if (!byYear.has(p.year)) byYear.set(p.year, []);
      byYear.get(p.year)!.push(p);
    }
    return [...byYear.entries()]
      .map(([year, rows]) => ({ year, rows: rows.sort((a, b) => b.month - a.month) }))
      .sort((a, b) => b.year - a.year);
  }, [periods]);

  useEffect(() => {
    if (!fund || !token) {
      setPeriods([]);
      return;
    }
    let cancelled = false;
    fetch(`/api/periods?fund=${fund.amfi_code}`, { headers: { 'x-embed-token': token } })
      .then((res) => res.json())
      .then((ps: PeriodRow[]) => {
        if (!cancelled) setPeriods(ps);
      })
      .catch(() => {
        if (!cancelled) setPeriods([]);
      });
    return () => {
      cancelled = true;
    };
  }, [fund, token]);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const disabled = !fund;
  const current = periods.find((p) => p.period === period);

  return (
    <div ref={wrapRef} className="relative shrink-0" data-testid="period-picker">
      <button
        disabled={disabled}
        onClick={() => {
          setOpen((o) => {
            const next = !o;
            // Jump straight to the currently-selected period's year (rather
            // than always landing on the year list) so re-opening to pick a
            // nearby month doesn't cost an extra click.
            if (next) setPickerYear(current?.year ?? null);
            return next;
          });
        }}
        className={[
          'flex items-center gap-2 h-9 px-3 bg-card border rounded-sm transition-colors focus-ring',
          disabled
            ? 'border-line-muted text-fg-disabled cursor-not-allowed'
            : 'border-line-default text-fg-default hover:bg-subtle',
        ].join(' ')}
      >
        <Calendar className="h-4 w-4 text-fg-secondary" strokeWidth={2} />
        <span className="font-mono text-[12px] tabular-nums min-w-[64px] text-left">
          {current ? labelFor(current) : period ?? 'Select month'}
        </span>
        <ChevronDown
          className={['h-4 w-4 text-fg-secondary transition-transform', open ? 'rotate-180' : ''].join(' ')}
          strokeWidth={2}
        />
      </button>

      {open && !disabled && (
        <div
          className="absolute right-0 top-[calc(100%+4px)] z-40 w-56 bg-card border border-line-subtle rounded-sm overflow-hidden anim-fade-up"
          style={{ boxShadow: 'var(--shadow-3)' }}
        >
          {pickerYear === null ? (
            <>
              <div className="px-3 py-2 border-b border-line-subtle bg-subtle">
                <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">Select year</span>
              </div>
              <ul className="py-1 max-h-72 overflow-y-auto scroll-thin">
                {years.map(({ year, rows }) => (
                  <li key={year}>
                    <button
                      onClick={() => setPickerYear(year)}
                      className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-subtle transition-colors"
                      data-testid={`period-year-${year}`}
                    >
                      <span className="font-mono text-[12px] tabular-nums text-fg-default">{year}</span>
                      <span className="font-mono text-[10px] text-fg-secondary">{rows.length}mo</span>
                    </button>
                  </li>
                ))}
                {years.length === 0 && (
                  <li className="px-3 py-2 font-mono text-[11px] text-fg-secondary">No months stored yet.</li>
                )}
              </ul>
            </>
          ) : (
            <>
              <button
                onClick={() => setPickerYear(null)}
                className="w-full flex items-center gap-1.5 px-3 py-2 border-b border-line-subtle bg-subtle hover:bg-line-subtle transition-colors"
                data-testid="period-year-back"
              >
                <ChevronLeft className="h-3.5 w-3.5 text-fg-secondary" strokeWidth={2} />
                <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">{pickerYear}</span>
              </button>
              <ul className="py-1 max-h-72 overflow-y-auto scroll-thin">
                {(years.find((y) => y.year === pickerYear)?.rows ?? []).map((p) => {
                  const active = p.period === period;
                  return (
                    <li key={p.period}>
                      <button
                        onClick={() => {
                          onSelect(p.period);
                          setOpen(false);
                        }}
                        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-subtle transition-colors"
                        data-testid={`period-option-${p.period}`}
                      >
                        <span className="flex items-center gap-2">
                          <Check
                            className={['h-3.5 w-3.5 text-primary', active ? 'opacity-100' : 'opacity-0'].join(' ')}
                            strokeWidth={2.5}
                          />
                          <span
                            className={[
                              'font-mono text-[12px] tabular-nums',
                              active ? 'text-fg-primary' : 'text-fg-default',
                            ].join(' ')}
                          >
                            {labelFor(p)}
                          </span>
                        </span>
                        <span className="font-mono text-[9px] tracking-meta uppercase text-success">saved</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

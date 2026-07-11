'use client';

// Layout ported from mf-analyser/components/FundContextBar.tsx (persistent bar
// docked above the main content: fund-switcher left, period picker right) —
// but the old app's fund-switcher slot (CuratedPicker, a fixed hardcoded
// dropdown) is NOT ported. Instead this uses a compact live-search input that
// opens the same dropdown-of-results UI as the SearchView home screen, via the
// shared useFundSearch hook, just docked/compact rather than full-page.
//
// Also carries the "Seed PPFAS (admin)" control + its in-page status banner —
// tucked here (small, right-aligned) rather than the prominent header spot it
// had in the old monolithic page.tsx, per the task brief.
import { useEffect, useRef, useState } from 'react';
import { Search, ChevronDown } from 'lucide-react';
import { useFund } from '@/components/FundProvider';
import { useFundSearch } from '@/hooks/use-fund-search';
import { PeriodPicker } from '@/components/PeriodPicker';
import type { SchemeMatch } from '@/lib/types';

function FundSwitcher() {
  const { fund, selectFund, token } = useFund();
  const [open, setOpen] = useState(false);
  const { query, setQuery, result, loading } = useFundSearch(token);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  function pick(m: SchemeMatch) {
    selectFund({
      amfi_code: m.amfi_code,
      scheme_name: m.scheme_name,
      amc_slug: m.amc_slug,
      category: m.category,
      asset_class: m.asset_class,
    });
    setQuery('');
    setOpen(false);
  }

  return (
    <div ref={wrapRef} className="relative flex-1 min-w-0 max-w-md" data-testid="fund-switcher">
      <div className="flex items-center gap-2 h-9 px-3 bg-card border border-line-default rounded-sm focus-within:border-line-focus">
        <Search className="h-3.5 w-3.5 text-fg-secondary shrink-0" strokeWidth={2} />
        <input
          value={open ? query : query || fund?.scheme_name || ''}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          placeholder="Search a fund…"
          className="flex-1 min-w-0 bg-transparent outline-none text-[13px] text-fg-default placeholder:text-fg-secondary font-sans"
          data-testid="fund-switcher-input"
        />
        <ChevronDown className="h-3.5 w-3.5 text-fg-secondary shrink-0" strokeWidth={2} />
      </div>

      {open && (
        <div
          className="absolute left-0 top-[calc(100%+4px)] z-40 w-full min-w-[280px] bg-card border border-line-subtle rounded-sm overflow-hidden anim-fade-up"
          style={{ boxShadow: 'var(--shadow-3)' }}
        >
          {loading && <div className="px-3 py-3 font-mono text-[11px] text-fg-secondary">Searching…</div>}
          {!loading && query.trim() === '' && (
            <div className="px-3 py-3 font-mono text-[11px] text-fg-secondary">Type to search funds…</div>
          )}
          {!loading && query.trim() !== '' && result.type === 'empty' && (
            <div className="px-3 py-3 font-mono text-[11px] text-fg-secondary">No match for &quot;{query}&quot;.</div>
          )}
          {!loading && result.type === 'name' && result.schemes.length > 0 && (
            <ul className="max-h-72 overflow-y-auto scroll-thin divide-y divide-line-subtle">
              {result.schemes.map((s) => (
                <li key={s.amfi_code}>
                  <button
                    onClick={() => pick(s)}
                    className="w-full flex flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-subtle transition-colors"
                    data-testid={`fund-switcher-option-${s.amfi_code}`}
                  >
                    <span className="text-[12.5px] text-fg-primary truncate w-full">{s.scheme_name}</span>
                    <span className="font-mono text-[10px] text-fg-secondary truncate w-full">
                      {s.amc_name} <span className="text-fg-disabled">·</span> {s.category}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function FundContextBar({
  seeding,
  seedStatus,
  onSeed,
}: {
  seeding: boolean;
  seedStatus: string | null;
  onSeed: () => void;
}) {
  const { fund, period, selectPeriod, token } = useFund();

  return (
    <div className="border-b border-line-subtle bg-card sticky top-0 z-30">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-2 sm:gap-3 flex-wrap">
        <FundSwitcher />
        {fund && <PeriodPicker fund={fund} period={period} onSelect={selectPeriod} token={token} />}
        <div className="flex-1" />
        <button
          onClick={onSeed}
          disabled={seeding}
          className="text-[10px] font-mono tracking-meta uppercase px-2.5 py-1.5 border border-line-subtle rounded-sm text-fg-secondary hover:bg-subtle disabled:opacity-50 shrink-0"
          data-testid="seed-ppfas-button"
        >
          {seeding ? 'Seeding…' : 'Seed PPFAS (admin)'}
        </button>
      </div>
      {seedStatus && (
        <div
          className={[
            'max-w-[1400px] mx-auto px-4 sm:px-6 pb-2.5 text-[11px] font-mono',
            seedStatus.startsWith('Seed failed') ? 'text-error' : 'text-success',
          ].join(' ')}
          data-testid="seed-status-banner"
        >
          {seedStatus}
        </div>
      )}
    </div>
  );
}

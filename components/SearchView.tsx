'use client';

// Ported layout from mf-analyser/components/SearchView.tsx (search input, "Full
// corpus search" eyebrow, results grouped by scheme) but rewired to this app's
// fresh /api/search route via useFundSearch, and to FundSummary/amfi_code
// instead of the old app's scheme id. The old file's disabled ISIN-lookup
// branch is dropped entirely, not carried over (it was dead code there).
// This is the home screen: idle/no fund+period selected yet renders this.
import { Search, ArrowRight } from 'lucide-react';
import { useFund } from '@/components/FundProvider';
import { useFundSearch } from '@/hooks/use-fund-search';
import type { FundSummary } from '@/lib/types';

// One-click shortcuts so a first-time viewer doesn't have to type anything to
// see the app in action. No usage/click tracking exists yet to rank real
// popularity, so these are manually curated well-known funds across
// different AMCs — swap the list as the corpus grows. Identities pulled from
// the live committed seed bundles (amfi_code is the ground truth key).
const POPULAR_FUNDS: FundSummary[] = [
  {
    amfi_code: '122639',
    scheme_name: 'Parag Parikh Flexi Cap Fund - Direct Plan - Growth',
    amc_slug: 'ppfas',
    category: 'Equity - Flexi Cap Fund',
    asset_class: 'equity',
  },
  {
    amfi_code: '118955',
    scheme_name: 'HDFC Flexi Cap Fund - Direct Plan - Growth',
    amc_slug: 'hdfc',
    category: 'Equity - Flexi Cap Fund',
    asset_class: 'equity',
  },
  {
    amfi_code: '108467',
    scheme_name: 'ICICI Prudential Bluechip Fund - Direct Plan - Growth',
    amc_slug: 'icici',
    category: 'Equity - Large Cap Fund',
    asset_class: 'equity',
  },
];

export function SearchView() {
  const { selectFund, token } = useFund();
  const { query, setQuery, result, loading, failed } = useFundSearch(token);

  function openScheme(m: FundSummary) {
    selectFund(m);
    // FundProvider's fund-change effect auto-resolves the latest stored period.
  }

  const empty = result.type === 'empty';

  return (
    <div>
      <div className="border-t border-line-subtle pt-8">
        <div className="font-mono text-[11px] tracking-meta uppercase text-fg-secondary mb-3">
          Full corpus search
        </div>
        <h1 className="font-sans text-[30px] sm:text-[38px] lg:text-[42px] leading-[1.05] font-semibold tracking-tight text-fg-primary max-w-3xl">
          Find any fund
        </h1>
        <p className="text-[14px] text-fg-secondary mt-3 leading-relaxed max-w-xl">
          Search across every ingested disclosure by fund name, AMC or category.
        </p>
      </div>

      <div className="mt-6 flex items-center gap-2 h-11 px-4 bg-card border border-line-default rounded-sm focus-within:border-line-focus">
        <Search className="h-4 w-4 text-fg-secondary shrink-0" strokeWidth={2} />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Parag Parikh Flexi Cap, HDFC, Small Cap…"
          className="flex-1 min-w-0 bg-transparent outline-none text-[15px] text-fg-default placeholder:text-fg-secondary font-sans"
          data-testid="corpus-search-input"
        />
      </div>

      {query.trim() === '' && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">Popular</span>
          {POPULAR_FUNDS.map((f) => (
            <button
              key={f.amfi_code}
              onClick={() => openScheme(f)}
              className="text-[12.5px] px-3 py-1.5 border border-line-subtle rounded-full text-fg-primary hover:bg-subtle hover:border-line-default transition-colors"
              data-testid={`popular-fund-${f.amfi_code}`}
            >
              {f.scheme_name.replace(' - Direct Plan - Growth', '')}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="mt-6 py-16 text-center font-mono text-[12px] text-fg-secondary">Searching corpus…</div>
      )}

      {!loading && failed && (
        <div className="mt-6 py-16 text-center font-mono text-[12px] text-fg-secondary">
          Couldn&apos;t search just now — try again.
        </div>
      )}

      {!loading && !failed && empty && query.trim() === '' && (
        <div className="mt-6 py-16 text-center font-mono text-[12px] text-fg-secondary">
          Type to search the full disclosure corpus…
        </div>
      )}

      {!loading && !failed && empty && query.trim() !== '' && (
        <div className="mt-6 py-16 text-center font-mono text-[12px] text-fg-secondary">
          No match for &quot;{query}&quot;.
        </div>
      )}

      {!loading && result.type === 'name' && result.schemes.length > 0 && (
        <div className="mt-6 space-y-8">
          <div>
            <div className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary mb-2">
              Funds ({result.schemes.length})
            </div>
            <ul className="bg-card border border-line-subtle rounded-sm divide-y divide-line-subtle overflow-hidden">
              {result.schemes.map((s) => (
                <li key={s.amfi_code}>
                  <button
                    onClick={() => openScheme(s)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-subtle transition-colors"
                    data-testid={`search-scheme-${s.amfi_code}`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] text-fg-primary truncate">{s.scheme_name}</div>
                      <div className="font-mono text-[11px] text-fg-secondary truncate">
                        {s.amc_name} <span className="text-fg-disabled">·</span> {s.category}
                      </div>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-fg-secondary shrink-0" strokeWidth={2} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

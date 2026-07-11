'use client';

// Composes the "ready" analyse view — mirrors mf-analyser/components/AnalyseView.tsx's
// section order (KPI grid -> portfolio characteristics -> interpretation ->
// allocation -> holdings) and SectionLabel styling, adapted to this app's data
// flow: fetches /api/changes (current + previous + kpis + changes + category_drift)
// once, then fires /api/ai/insight fire-and-forget so it never blocks the rest
// of the page — same pattern as the old AnalyseView's fetchAIInsight call.
import { useEffect, useState } from 'react';
import { Search, FileWarning } from 'lucide-react';
import { useFund } from '@/components/FundProvider';
import { ResultsHeader } from '@/components/ResultsHeader';
import { KpiTile } from '@/components/KpiTile';
import { AIInsightPanel } from '@/components/AIInsightPanel';
import { ChangesPanel, ChangesUnavailable } from '@/components/ChangesPanel';
import { AssetAllocationBar } from '@/components/AssetAllocationBar';
import { CategoryDonut } from '@/components/CategoryDonut';
import { MarketCapBar } from '@/components/MarketCapBar';
import { TopHoldings } from '@/components/TopHoldings';
import { HoldingsTable } from '@/components/HoldingsTable';
import { CollapsibleSection } from '@/components/CollapsibleSection';
import { ProgressTerminal } from '@/components/ProgressTerminal';
import { MetricsStrip, RatingBreakdown, SectionLabel } from '@/components/AnalyseMeta';
import type { AIInsight, ChangesData } from '@/lib/types';

const fmtCr = (n: number | null) => (n == null ? '—' : '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 }));
const fmtNav = (n: number | null) =>
  n == null ? '—' : '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtPct = (n: number | null) => (n == null ? '—' : n.toFixed(2) + '%');

function donutMeta(asset: string) {
  if (asset === 'equity')
    return {
      title: 'Sector Allocation',
      center: 'Sectors',
      caption: 'Which industries the fund’s equity holdings are concentrated in.',
    };
  if (asset === 'debt')
    return {
      title: 'Instrument Mix',
      center: 'Types',
      caption: 'The mix of debt instrument types (bonds, CDs, government paper, etc.) the fund holds.',
    };
  return {
    title: 'Category Breakdown',
    center: 'Categories',
    caption: 'How the fund’s holdings are split across broad portfolio categories.',
  };
}

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { ...(init?.headers ?? {}), 'x-embed-token': token } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ error: res.statusText }))).error ?? res.statusText);
  return res.json() as Promise<T>;
}

// Separate from api<T>() above because /api/ai/insight's error body can carry
// a `code` (e.g. "INSUFFICIENT_CREDITS" on a 402) that needs special-casing
// into a clearer message — see app/api/ai/insight/route.ts.
async function fetchAIInsight(fund: string, period: string, token: string): Promise<AIInsight> {
  const res = await fetch('/api/ai/insight', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-embed-token': token },
    body: JSON.stringify({ fund, period }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    if (body.code === 'INSUFFICIENT_CREDITS') throw new Error('Out of AI credits.');
    throw new Error(body.error ?? res.statusText);
  }
  return res.json() as Promise<AIInsight>;
}

export function AnalyseContent() {
  const { fund, period, token } = useFund();
  const [data, setData] = useState<ChangesData | null>(null);
  const [ai, setAi] = useState<AIInsight | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [aiError, setAiError] = useState<string | null>(null);

  function loadAI(fundCode: string, periodVal: string, tok: string) {
    setAiStatus('loading');
    setAiError(null);
    fetchAIInsight(fundCode, periodVal, tok)
      .then((insight) => {
        setAi(insight);
        setAiStatus('ready');
      })
      .catch((e: Error) => {
        setAiStatus('error');
        setAiError(e.message);
      });
  }

  useEffect(() => {
    if (!fund || !period || !token) return;
    setStatus('loading');
    setError(null);
    setData(null);
    setAi(null);
    setAiStatus('loading');
    setAiError(null);
    api<ChangesData>(`/api/changes?fund=${fund.amfi_code}&period=${period}`, token)
      .then((d) => {
        setData(d);
        setStatus('ready');
        // Never blocks the rest of the page from rendering — the deterministic
        // data above is already set — but failures are now surfaced with a
        // retry rather than hanging on "Generating…" forever.
        loadAI(fund.amfi_code, period, token);
      })
      .catch((e: Error) => {
        setStatus('error');
        setError(e.message);
      });
  }, [fund?.amfi_code, period, token]);

  if (!fund || !period) {
    return (
      <div className="max-w-xl mx-auto py-20 text-center">
        <div className="inline-flex h-12 w-12 items-center justify-center bg-subtle border border-line-subtle rounded-sm mb-5">
          <Search className="h-6 w-6 text-fg-secondary" strokeWidth={1.75} />
        </div>
        <h2 className="font-sans text-[28px] font-semibold tracking-tight text-fg-primary">Choose a fund to begin</h2>
        <p className="text-[14px] text-fg-secondary mt-3 leading-relaxed">
          Search for a fund above, or use the corpus search below.
        </p>
      </div>
    );
  }

  if (status === 'loading') {
    return (
      <div className="py-14">
        <ProgressTerminal
          scheme={fund.amfi_code}
          steps={['fetching portfolio…', 'computing month-over-month changes…', 'generating AI interpretation…']}
          current={1}
        />
      </div>
    );
  }

  if (status === 'error' || !data) {
    return (
      <div className="max-w-xl mx-auto py-20 text-center">
        <div className="inline-flex h-12 w-12 items-center justify-center bg-tint-error border border-line-subtle rounded-sm mb-5">
          <FileWarning className="h-6 w-6 text-error" strokeWidth={1.75} />
        </div>
        <h2 className="font-sans text-[28px] font-semibold tracking-tight text-fg-primary">No portfolio for this month</h2>
        <p className="text-[14px] text-fg-secondary mt-3 leading-relaxed">{error ?? 'Try a different month.'}</p>
      </div>
    );
  }

  const d = data.current;
  const meta = donutMeta(d.asset_class);
  const isEquity = d.market_cap_breakdown.length > 0;

  return (
    <div>
      <ResultsHeader data={d} />

      <section className="pt-8 sm:pt-9">
        <SectionLabel>Key Metrics</SectionLabel>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4 lg:gap-6" data-testid="kpi-grid">
          <KpiTile
            label="AUM"
            value={d.aum != null ? `${fmtCr(d.aum)} Cr` : '—'}
            hint="Assets under management"
            tooltip="Total money all investors have put into this fund."
          />
          <KpiTile
            label="NAV"
            value={fmtNav(d.nav)}
            hint={`as of ${d.period_label}`}
            tooltip="Net Asset Value — the price of one unit of the fund."
          />
          <KpiTile
            label="Expense Ratio"
            value={fmtPct(d.expense_ratio)}
            hint="Annual, regular plan"
            tooltip="The annual fee you pay, as a % of your investment, for the fund to manage your money."
          />
          <KpiTile
            label="Holdings"
            value={String(d.holdings_count)}
            hint="Disclosed instruments"
            tooltip="The number of distinct positions (stocks, bonds, cash instruments, etc.) the fund discloses holding."
          />
          <KpiTile
            label="Deployable Cash"
            value={fmtPct(d.deployable_cash)}
            hint="Cash + equivalents"
            tooltip="The % of the fund parked in cash or cash-like instruments (TREPS, T-Bills) rather than invested in securities."
            accent
          />
          <KpiTile
            label="Total Weight"
            value={fmtPct(d.total_weight)}
            hint="Disclosure coverage"
            tooltip="What % of the fund's holdings we could confirm from the disclosure — should be close to 100%."
          />
        </div>
      </section>

      {d.metrics && <MetricsStrip metrics={d.metrics} />}

      <section className="pt-8 sm:pt-9 mt-8 sm:mt-9 border-t border-line-subtle">
        <SectionLabel>Interpretation</SectionLabel>
        <div className="grid md:grid-cols-2 gap-4 items-stretch">
          <div className="overflow-y-auto scroll-thin" style={{ maxHeight: '420px' }}>
            {aiStatus === 'ready' && ai ? (
              <AIInsightPanel insight={ai} data={d} />
            ) : aiStatus === 'error' ? (
              <div
                className="bg-card border border-line-subtle rounded-sm h-full flex flex-col items-center justify-center gap-3 px-4 py-8 text-center"
                data-testid="ai-error"
              >
                <span className="text-[12.5px] text-error">{aiError ?? 'Could not generate AI interpretation.'}</span>
                <button
                  type="button"
                  onClick={() => fund && period && token && loadAI(fund.amfi_code, period, token)}
                  className="font-mono text-[11px] tracking-meta uppercase border border-line-default rounded-sm px-3 py-1.5 hover:bg-subtle transition-colors focus-ring"
                  data-testid="ai-retry"
                >
                  Retry
                </button>
              </div>
            ) : (
              <div className="bg-card border border-line-subtle rounded-sm h-full flex items-center justify-center px-4 py-8 text-center">
                <span className="text-[12.5px] text-fg-secondary">Generating AI interpretation…</span>
              </div>
            )}
          </div>
          {data.previous ? (
            <ChangesPanel data={data} fromLabel={data.previous.period_label} toLabel={d.period_label} />
          ) : (
            <ChangesUnavailable message="No prior month stored yet for this fund — changes will show once a second month is loaded." />
          )}
        </div>
      </section>

      <section className="pt-8 sm:pt-9 mt-8 sm:mt-9 border-t border-line-subtle">
        <SectionLabel>Allocation</SectionLabel>
        <AssetAllocationBar data={d.asset_allocation} />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-3 gap-4 mt-4">
          <div className="md:col-span-2 lg:col-span-2">
            <CategoryDonut data={d.category_breakdown} title={meta.title} centerLabel={meta.center} caption={meta.caption} />
          </div>
          <div className="space-y-4 md:col-span-2 lg:col-span-1">
            {isEquity && <MarketCapBar data={d.market_cap_breakdown} />}
            {d.rating_breakdown && d.rating_breakdown.length > 0 && <RatingBreakdown data={d.rating_breakdown} />}
            <div className="bg-card border border-line-subtle rounded-sm p-4">
              <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary mb-3">Cash Composition</h3>
              <div className="space-y-2">
                {d.cash_breakdown.map((c) => (
                  <div key={c.section} className="flex items-center justify-between">
                    <span className="text-[12.5px] text-fg-default">{c.section}</span>
                    <span className="font-mono text-[12px] text-fg-primary tabular-nums">{c.weight.toFixed(2)}%</span>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2 border-t border-line-subtle">
                  <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">Deployable</span>
                  <span className="font-mono text-[12px] text-success tabular-nums">{d.deployable_cash.toFixed(2)}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <CollapsibleSection
        className="pt-8 sm:pt-9 mt-8 sm:mt-9 border-t border-line-subtle"
        label="Holdings"
        right={
          <span className="font-mono text-[10px] tracking-meta uppercase text-fg-disabled shrink-0">
            {d.holdings_count} positions
          </span>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1">
            <TopHoldings data={d.top_holdings} totalCount={d.holdings_count} holdings={d.holdings} />
          </div>
          <div className="lg:col-span-2">
            <HoldingsTable data={d.holdings} />
          </div>
        </div>
      </CollapsibleSection>
    </div>
  );
}

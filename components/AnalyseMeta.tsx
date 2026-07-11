'use client';

// Split out of AnalyseContent.tsx to keep that file under ~200 lines — ported
// from mf-analyser/components/AnalyseView.tsx's MetricsStrip/RatingBreakdown
// (portfolio-wide aggregates a factsheet states directly, not derived from
// holdings). Both are optional on AnalyseData (mf-lookr/lib/types.ts).
import type { PortfolioMetrics, WeightItem } from '@/lib/types';

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="font-mono text-[10px] tracking-wide2 uppercase text-fg-secondary mb-4">{children}</div>;
}

export function MetricsStrip({ metrics }: { metrics: PortfolioMetrics }) {
  const nums: { label: string; value: string }[] = [];
  if (metrics.ytm != null) nums.push({ label: 'YTM', value: metrics.ytm.toFixed(2) + '%' });
  if (metrics.macaulay_days != null) nums.push({ label: 'Macaulay Dur.', value: `${metrics.macaulay_days}d` });
  if (metrics.residual_days != null) nums.push({ label: 'Avg Residual', value: `${metrics.residual_days}d` });

  const text: { label: string; value: string }[] = [];
  if (metrics.benchmark) text.push({ label: 'Benchmark', value: metrics.benchmark });
  if (metrics.inception) text.push({ label: 'Inception', value: metrics.inception });
  if (metrics.fund_managers) text.push({ label: 'Fund Manager', value: metrics.fund_managers });

  if (nums.length === 0 && text.length === 0) return null;

  return (
    <section className="pt-8 sm:pt-9 mt-8 sm:mt-9 border-t border-line-subtle">
      <SectionLabel>Portfolio Characteristics</SectionLabel>
      <div className="bg-card border border-line-subtle rounded-sm overflow-hidden">
        {nums.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 divide-x divide-line-subtle border-b border-line-subtle">
            {nums.map((it) => (
              <div key={it.label} className="px-3 py-2.5">
                <div className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">{it.label}</div>
                <div className="font-mono text-[16px] text-fg-primary tabular-nums leading-tight mt-0.5">{it.value}</div>
              </div>
            ))}
          </div>
        )}
        {text.map((it) => (
          <div key={it.label} className="flex items-baseline gap-3 px-3 py-2 border-b border-line-subtle last:border-0">
            <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary w-28 shrink-0">{it.label}</span>
            <span className="font-mono text-[12px] text-fg-primary">{it.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RatingBreakdown({ data }: { data: WeightItem[] }) {
  const max = Math.max(...data.map((d) => Math.abs(d.weight)), 1);
  return (
    <div className="bg-card border border-line-subtle rounded-sm p-4">
      <h3 className="font-mono text-[11px] tracking-wide2 uppercase text-fg-secondary mb-3">By Rating Class</h3>
      <div className="space-y-2.5">
        {data.map((d) => (
          <div key={d.name}>
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[12px] text-fg-default leading-tight">{d.name}</span>
              <span className="font-mono text-[12px] text-fg-primary tabular-nums shrink-0">{d.weight.toFixed(2)}%</span>
            </div>
            <span className="block h-1 w-full bg-muted rounded-sm overflow-hidden">
              <span
                className={['block h-full rounded-sm', d.weight < 0 ? 'bg-warning' : 'bg-primary'].join(' ')}
                style={{ width: `${(Math.abs(d.weight) / max) * 100}%` }}
              />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export { SectionLabel };

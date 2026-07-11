'use client';

import { useState } from 'react';
import { Sparkles, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react';
import type { AIInsight, AnalyseData, AssetClass } from '@/lib/types';

function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
}

const ASSET_LABEL: Record<AssetClass, string> = { equity: 'Equity', debt: 'Debt', hybrid: 'Hybrid', other: 'Mixed' };

// Quantitative highlights pulled straight from the snapshot (not the model) — the
// numbers an operator scans first. The AI prose lives behind the expand toggle.
// Note: mf-lookr's AnalyseData has no `partial` flag (the old app's top-N-only
// disclosure concept) — this app's source policy is full detailed disclosures
// only, so that chip/branch is dropped rather than ported.
function chipsFor(d: AnalyseData): { label: string; value: string }[] {
  const c: { label: string; value: string }[] = [
    { label: 'Posture', value: ASSET_LABEL[d.asset_class] },
    { label: 'Coverage', value: `${d.total_weight.toFixed(1)}%` },
    { label: 'Deployable', value: `${d.deployable_cash.toFixed(1)}%` },
  ];
  if (d.metrics?.ytm != null) c.push({ label: 'YTM', value: `${d.metrics.ytm.toFixed(2)}%` });
  if (d.metrics?.macaulay_days != null) c.push({ label: 'Duration', value: `${d.metrics.macaulay_days}d` });
  return c;
}

export function AIInsightPanel({ insight, data }: { insight: AIInsight; data: AnalyseData }) {
  const [open, setOpen] = useState(false);
  const chips = chipsFor(data);
  const flagN = insight.flags.length;

  return (
    <section className="bg-card border border-line-default rounded-sm" data-testid="ai-insight-panel">
      {/* Header — single line */}
      <div className="flex items-center gap-2.5 px-3 h-9 border-b border-line-subtle">
        <span className="inline-flex items-center gap-1.5 bg-primary text-primary-fg font-mono text-[10px] tracking-meta uppercase px-2 py-0.5 rounded-sm">
          <Sparkles className="h-3 w-3" strokeWidth={2.25} />
          AI Read
        </span>
        <span className="font-mono text-[10px] tracking-meta uppercase text-fg-disabled truncate hidden sm:inline">
          {fmtTime(insight.generated_at)}
        </span>
        <div className="flex-1" />
        {flagN > 0 && (
          <span className="inline-flex items-center gap-1 font-mono text-[10px] tracking-meta uppercase text-warning">
            <AlertTriangle className="h-3 w-3" strokeWidth={2.25} />
            {flagN} flag{flagN > 1 ? 's' : ''}
          </span>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 font-mono text-[10px] tracking-meta uppercase text-primary-hover hover:text-primary-pressed focus-ring rounded-sm px-1 shrink-0"
          data-testid="ai-toggle"
        >
          {open ? 'Less' : 'Detail'}
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Collapsed signal strip: headline + metric chips */}
      <div className="px-3 py-2.5 flex flex-col gap-2">
        <p className="text-[13px] leading-snug text-fg-primary line-clamp-2">{insight.headline}</p>
        <div className="flex flex-wrap gap-1.5">
          {chips.map((c) => (
            <span
              key={c.label}
              className="inline-flex items-baseline gap-1.5 border border-line-subtle rounded-sm px-1.5 py-0.5 bg-subtle"
            >
              <span className="font-mono text-[9px] tracking-meta uppercase text-fg-secondary">{c.label}</span>
              <span className="font-mono text-[11px] text-fg-primary tabular-nums">{c.value}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Expanded detail */}
      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-line-subtle anim-fade-up">
          <div className="grid md:grid-cols-2 2xl:grid-cols-3 gap-x-6 gap-y-3 mt-2">
            {insight.sections.map((s) => (
              <div key={s.title}>
                <h4 className="font-mono text-[10px] tracking-meta uppercase text-primary-hover mb-1.5">{s.title}</h4>
                <ul className="space-y-1">
                  {s.bullets.map((b, i) => (
                    <li key={i} className="flex gap-1.5 text-[12.5px] leading-snug text-fg-default">
                      <span className="text-primary select-none shrink-0">—</span>
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          {flagN > 0 && (
            <div className="mt-3 bg-tint-warning border-l-2 border-warning rounded-sm px-3 py-2">
              <h4 className="font-mono text-[10px] tracking-meta uppercase text-warning mb-1.5">Watch-outs</h4>
              <ul className="space-y-1">
                {insight.flags.map((f, i) => (
                  <li key={i} className="flex gap-1.5 text-[12.5px] leading-snug text-fg-default">
                    <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" strokeWidth={2} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

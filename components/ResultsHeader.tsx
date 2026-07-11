'use client';

import { ArrowUpRight } from 'lucide-react';
import { SourceBadge } from './SourceBadge';
import type { AnalyseData } from '@/lib/types';

const ASSET_LABEL: Record<string, string> = {
  equity: 'Equity',
  debt: 'Debt',
  hybrid: 'Hybrid',
  other: 'Other',
};

// Saturated content block colour by asset class — all carry white text
const BLOCK: Record<string, string> = {
  equity: 'var(--cat-1)', // electric blue
  debt: 'var(--cat-6)', // navy slate
  hybrid: 'var(--cat-4)', // forest
  other: 'var(--cat-5)', // orange
};

export function ResultsHeader({ data }: { data: AnalyseData }) {
  return (
    <div className="border-t border-line-subtle pt-8">
      <div className="flex flex-col sm:flex-row gap-5 sm:gap-7 lg:gap-10">
        {/* Signature colour block */}
        <a
          href={data.source_url}
          target="_blank"
          rel="noreferrer"
          className="group relative shrink-0 w-full sm:w-[160px] lg:w-[208px] aspect-[16/9] sm:aspect-square rounded-sm overflow-hidden focus-ring"
          style={{ background: BLOCK[data.asset_class] }}
          data-testid="fund-block"
        >
          <div className="absolute inset-0 p-4 flex flex-col justify-between text-white">
            <span className="font-mono text-[10px] tracking-wide2 uppercase text-white/75">
              {ASSET_LABEL[data.asset_class]} Fund
            </span>
            <div className="flex items-end justify-between gap-2">
              <span className="text-[17px] font-semibold leading-tight tracking-tight max-w-[80%]">
                {data.category}
              </span>
              <ArrowUpRight className="h-5 w-5 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" strokeWidth={2} />
            </div>
          </div>
        </a>

        {/* Headline + meta */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-3">
            <span className="font-mono text-[11px] tracking-meta uppercase text-fg-secondary tabular-nums">
              {data.period_label}
            </span>
            <SourceBadge sourceOrg={data.source_org} asOf={data.as_of_date} />
          </div>
          <h1 className="font-sans text-[26px] sm:text-[34px] lg:text-[46px] leading-[1.04] font-semibold tracking-tight text-fg-primary max-w-3xl">
            {data.scheme_name}
          </h1>
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 mt-4 font-mono text-[12px] text-fg-secondary">
            <span className="text-fg-default">{data.amc_name}</span>
            <span className="text-fg-disabled">·</span>
            <span>{data.category}</span>
            <span className="text-fg-disabled">·</span>
            <span className="tabular-nums">{data.isin}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

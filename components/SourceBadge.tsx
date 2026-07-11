'use client';

import { Database } from 'lucide-react';

function fmtDate(iso: string) {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function SourceBadge({ sourceOrg, asOf }: { sourceOrg: string; asOf: string }) {
  return (
    <div
      className="inline-flex items-center gap-2 h-7 px-2.5 bg-subtle border border-line-subtle rounded-sm"
      data-testid="source-badge"
    >
      <Database className="h-3.5 w-3.5 text-fg-secondary" strokeWidth={2} />
      <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">
        Sourced from {sourceOrg}
      </span>
      <span className="text-fg-disabled">·</span>
      <span className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">
        as of {fmtDate(asOf)}
      </span>
    </div>
  );
}

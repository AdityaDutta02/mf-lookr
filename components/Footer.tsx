'use client';

import { BarChart3 } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-line-subtle bg-card mt-4">
      <div className="max-w-[1400px] mx-auto px-6 py-7">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="h-6 w-6 bg-ink flex items-center justify-center rounded-sm">
              <BarChart3 className="h-3.5 w-3.5 text-fg-inverse" strokeWidth={2.25} />
            </div>
            <span className="font-mono text-[11px] tracking-wide2 uppercase text-fg-primary">
              MF Lookr
            </span>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-x-6 gap-y-1.5">
            <p className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">
              Fund house → fund → year → month <span className="text-fg-disabled">·</span> No login
            </p>
            <p className="font-mono text-[10px] tracking-meta uppercase text-fg-secondary">
              Not investment advice <span className="text-fg-disabled">·</span> Verify against official factsheet
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}

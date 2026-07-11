'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

/**
 * Section whose body collapses on mobile to shorten scroll.
 * - Mobile (<lg): tappable header with chevron; body hidden until expanded (collapsed by default).
 * - Desktop (lg+): body always shown via `lg:block`; header is inert (no chevron, no pointer).
 * `right` (e.g. a count summary or legend) stays visible at every width, even when collapsed.
 */
export function CollapsibleSection({
  label,
  right,
  children,
  className = '',
}: {
  label: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <section className={className}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 mb-4 lg:cursor-default focus-ring rounded-sm text-left"
      >
        <span className="flex items-center gap-1.5 min-w-0">
          <ChevronDown
            className={[
              'h-3.5 w-3.5 text-fg-secondary shrink-0 transition-transform lg:hidden',
              open ? '' : '-rotate-90',
            ].join(' ')}
            strokeWidth={2}
          />
          <span className="font-mono text-[10px] tracking-wide2 uppercase text-fg-secondary truncate">{label}</span>
        </span>
        {right}
      </button>
      <div className={[open ? 'block' : 'hidden', 'lg:block'].join(' ')}>{children}</div>
    </section>
  );
}

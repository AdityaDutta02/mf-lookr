'use client';

// Shared pill used everywhere a holding name renders (ChangesPanel,
// HoldingsTable, TopHoldings) so money-market paper (CD/CP/T-Bill/G-Sec/
// TREPS/etc.) is never visually confusable with the equity share of the same
// issuer — see task brief bug 3. Equity is treated as the default/unmarked
// case (it's the majority and the norm) and renders no tag at all.
const META: Record<string, { label: string; tooltip: string; tone: "warning" | "info" }> = {
  cd: {
    label: "CD",
    tooltip:
      "Short-term debt paper issued by this company, not its stock — a different investment that regularly matures and rolls over, unrelated to any equity position in the same name.",
    tone: "warning",
  },
  cp: {
    label: "CP",
    tooltip:
      "Short-term debt paper issued by this company, not its stock — a different investment that regularly matures and rolls over, unrelated to any equity position in the same name.",
    tone: "warning",
  },
  corporate_debt: {
    label: "Bond",
    tooltip: "Long-term debt issued by this company — a loan to it, not an ownership stake.",
    tone: "warning",
  },
  tbill: { label: "T-Bill", tooltip: "Government-issued debt, not a company holding.", tone: "info" },
  gsec: { label: "G-Sec", tooltip: "Government-issued debt, not a company holding.", tone: "info" },
  treps: {
    label: "TREPS",
    tooltip: "Very short-term (overnight-ish) secured lending — parked cash, not a security pick.",
    tone: "info",
  },
  fund: { label: "Fund", tooltip: "A unit of another mutual fund/ETF held by this portfolio.", tone: "info" },
  reit: { label: "REIT", tooltip: "A real-estate investment trust unit — property exposure, not a company stock.", tone: "info" },
  derivative: {
    label: "Derivative",
    tooltip: "A futures/options contract used for hedging or exposure — not a direct holding.",
    tone: "warning",
  },
};

const TONE_CLS: Record<string, string> = {
  warning: "text-warning border-line-subtle bg-tint-warning",
  info: "text-info border-tint-info-border bg-tint-info",
};

export function InstrumentTag({ type, className }: { type?: string | null; className?: string }) {
  if (!type) return null;
  const meta = META[type.toLowerCase()];
  // Equity (and any unrecognised/unmapped type) is the default case — no tag.
  if (!meta) return null;
  return (
    <span
      className={[
        "inline-flex items-center font-mono text-[9px] tracking-meta uppercase px-1 py-[1px] rounded-sm border shrink-0 cursor-help",
        TONE_CLS[meta.tone],
        className ?? "",
      ].join(" ")}
      title={meta.tooltip}
      data-testid={`instrument-tag-${type.toLowerCase()}`}
    >
      {meta.label}
    </span>
  );
}

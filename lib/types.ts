// Canonical data contract — carried over from the old app's ARCHITECTURE.md /
// snapshots.data shape (lib/types.ts in mf-analyser), unchanged. This is what
// the local extraction toolkit (tools/) produces per (fund, period) and what
// disclosures.data stores.

export type AssetClass = "equity" | "debt" | "hybrid" | "other";

export interface WeightItem {
  name: string;
  weight: number;
}
export interface CashItem {
  section: string;
  weight: number;
}
export interface TopHolding {
  name: string;
  isin: string;
  sector: string;
  weight: number;
}
export interface Holding {
  name: string;
  isin: string;
  instrument_type: string;
  sector: string;
  weight: number;
  market_value: number; // ₹ cr
  quantity: number;
}

// Portfolio-wide characteristics stated as aggregates on a factsheet
// (not derivable from disclosed holdings). All optional.
export interface PortfolioMetrics {
  ytm: number | null; // annualised portfolio YTM, %
  macaulay_days: number | null; // Macaulay duration, days
  residual_days: number | null; // average residual maturity, days
  benchmark: string | null;
  inception: string | null; // as printed
  fund_managers: string | null; // as printed
}

export interface AnalyseData {
  amfi_code: string;
  scheme_name: string;
  amc_name: string;
  category: string;
  isin: string;
  asset_class: AssetClass;
  period: string; // "YYYY-MM"
  period_label: string; // "May 2026"
  as_of_date: string;
  source_org: string;
  source_url: string;
  aum: number | null; // ₹ cr
  nav: number | null;
  expense_ratio: number | null;
  holdings_count: number;
  total_weight: number;
  deployable_cash: number; // %
  asset_allocation: WeightItem[];
  category_breakdown: WeightItem[];
  market_cap_breakdown: WeightItem[]; // equity only; may be []
  cash_breakdown: CashItem[];
  top_holdings: TopHolding[];
  holdings: Holding[];
  rating_breakdown?: WeightItem[]; // portfolio-wide by credit-rating class
  metrics?: PortfolioMetrics;
}

export interface AIInsight {
  generated_at: string;
  headline: string;
  sections: { title: string; bullets: string[] }[];
  flags: string[];
}

export interface AmcSummary {
  slug: string;
  name: string;
  status: "pending" | "loaded";
  fund_count: number;
}

export interface FundSummary {
  amfi_code: string;
  scheme_name: string;
  amc_slug: string;
  category: string;
  asset_class: AssetClass;
}

// Change/narrative payload — a fund's month vs the immediately-prior stored month.
export interface ChangeRow {
  name: string;
  isin: string;
  weight_a: number;
  weight_b: number;
  delta: number;
  // Share/unit count, not just %-of-NAV weight — lets a reader tell an actual
  // buy/sell from a position merely drifting with price. Only populated when the
  // source discloses quantity (the PPFAS "Detailed Portfolio Disclosure" XLS does;
  // the factsheet PDF does not — see tools/parse_ppfas.py vs parse_ppfas_xlsx.py).
  quantity_a: number | null;
  quantity_b: number | null;
  quantity_delta: number | null;
  quantity_delta_pct: number | null; // % change in quantity, independent of NAV/price moves
  // Additive — carried over from the source Holding so the UI can tag CD/CP/
  // T-Bill/G-Sec/TREPS rows distinctly from equity (see InstrumentTag).
  instrument_type?: string;
}
export interface ChangesData {
  current: AnalyseData;
  previous: AnalyseData | null; // null when this is the earliest stored month for the fund
  kpis: { cash_delta: number; count_delta: number; equity_delta: number; aum_delta: number | null } | null;
  changes: { added: ChangeRow[]; exited: ChangeRow[]; increased: ChangeRow[]; reduced: ChangeRow[] } | null;
  category_drift: WeightItem[] | null;
}

// Additive — search UI + /api/search contract. Never remove/rename existing
// fields above; only append here.
export interface SchemeMatch {
  amfi_code: string;
  scheme_name: string;
  amc_name: string;
  amc_slug: string;
  category: string;
  asset_class: AssetClass;
}
export type SearchResult = { type: "empty" } | { type: "name"; schemes: SchemeMatch[] };

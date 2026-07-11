// Shared month-over-month diff logic — extracted from app/api/changes/route.ts
// so app/api/ai/insight/route.ts can reuse the exact same deterministic
// computation (added/exited/increased/reduced + KPI deltas + category drift)
// instead of duplicating the DB/diff logic or round-tripping HTTP to itself.
import type { AnalyseData, ChangeRow, ChangesData, WeightItem } from "@/lib/types";

export const round2 = (n: number) => Math.round(n * 100) / 100;

export const equityPct = (d: AnalyseData) =>
  d.asset_allocation.filter((a) => /equity/i.test(a.name)).reduce((s, a) => s + a.weight, 0);

const normName = (s: string) => s.trim().toLowerCase().replace(/[.,]/g, "").replace(/\s+/g, " ");

// Quantity is only meaningful when both sides disclosed a nonzero share/unit count
// (0 is the sentinel the parser writes for "not disclosed" — TREPS/cash rows,
// or any source that lacks quantity entirely, like the factsheet PDF).
function quantityFields(qa: number | undefined, qb: number | undefined) {
  const known_a = qa != null && qa > 0;
  const known_b = qb != null && qb > 0;
  const quantity_a = known_a ? qa! : null;
  const quantity_b = known_b ? qb! : null;
  if (!known_a && !known_b) return { quantity_a, quantity_b, quantity_delta: null, quantity_delta_pct: null };
  const delta = (quantity_b ?? 0) - (quantity_a ?? 0);
  const pct = quantity_a && quantity_a !== 0 ? round2((delta / quantity_a) * 100) : null;
  return { quantity_a, quantity_b, quantity_delta: Math.round(delta * 100) / 100, quantity_delta_pct: pct };
}

export function diffHoldings(a: AnalyseData, b: AnalyseData) {
  const keyOf = (h: { isin: string; name: string }) => (h.isin && h.isin !== "—" ? h.isin : normName(h.name));
  const mapA = new Map(a.holdings.map((h) => [keyOf(h), h]));
  const mapB = new Map(b.holdings.map((h) => [keyOf(h), h]));
  const added: ChangeRow[] = [];
  const exited: ChangeRow[] = [];
  const increased: ChangeRow[] = [];
  const reduced: ChangeRow[] = [];
  for (const [k, hb] of mapB) {
    const ha = mapA.get(k);
    if (!ha) {
      added.push({
        name: hb.name, isin: hb.isin, weight_a: 0, weight_b: hb.weight, delta: round2(hb.weight),
        ...quantityFields(undefined, hb.quantity),
      });
      continue;
    }
    const delta = round2(hb.weight - ha.weight);
    const qf = quantityFields(ha.quantity, hb.quantity);
    const row = { name: hb.name, isin: hb.isin, weight_a: ha.weight, weight_b: hb.weight, delta, ...qf };
    // A position's weight drifts every month purely from price movement even when the
    // manager touched nothing — e.g. HDFC Bank's share count can be byte-for-byte
    // identical between two months while its NAV weight moves >0.4% just because the
    // stock re-rated. Bucketing that as "Increased" reads as manager activity when it
    // isn't. So: when BOTH months disclose quantity for this holding, "did the position
    // change" means "did the share count change" — bucket by quantity_delta, not weight
    // delta, and drop it from the list entirely when quantity is unchanged (nothing to
    // report). Only fall back to weight-delta bucketing when quantity isn't disclosed on
    // one/both sides (cash-like entries such as TREPS or Net Receivables/Payables).
    if (qf.quantity_a != null && qf.quantity_b != null) {
      if (qf.quantity_delta! > 0) increased.push(row);
      else if (qf.quantity_delta! < 0) reduced.push(row);
      // quantity_delta === 0 -> real weight drift from price, not a position change; omit.
    } else {
      if (delta > 0.01) increased.push(row);
      else if (delta < -0.01) reduced.push(row);
    }
  }
  for (const [k, ha] of mapA) {
    if (!mapB.has(k)) {
      exited.push({
        name: ha.name, isin: ha.isin, weight_a: ha.weight, weight_b: 0, delta: round2(-ha.weight),
        ...quantityFields(ha.quantity, undefined),
      });
    }
  }
  const magnitude = (r: ChangeRow) => Math.abs(r.quantity_delta_pct ?? r.delta);
  const byMagnitude = (x: ChangeRow, y: ChangeRow) => magnitude(y) - magnitude(x);
  return {
    added: added.sort(byMagnitude),
    exited: exited.sort(byMagnitude),
    increased: increased.sort(byMagnitude),
    reduced: reduced.sort(byMagnitude),
  };
}

export function categoryDrift(a: AnalyseData, b: AnalyseData): WeightItem[] {
  const wa = new Map(a.category_breakdown.map((c) => [c.name, c.weight]));
  const names = new Set([...a.category_breakdown, ...b.category_breakdown].map((c) => c.name));
  const out: WeightItem[] = [];
  for (const name of names) {
    const delta = round2((b.category_breakdown.find((c) => c.name === name)?.weight ?? 0) - (wa.get(name) ?? 0));
    if (Math.abs(delta) >= 0.05) out.push({ name, weight: delta });
  }
  return out.sort((x, y) => Math.abs(y.weight) - Math.abs(x.weight));
}

// Builds the full ChangesData payload from a (prior, current) pair. `prior` may
// be null when `current` is the earliest stored month for the fund.
export function buildChangesData(current: AnalyseData, prior: AnalyseData | null): ChangesData {
  if (!prior) {
    return { current, previous: null, kpis: null, changes: null, category_drift: null };
  }
  return {
    current,
    previous: prior,
    kpis: {
      cash_delta: round2(current.deployable_cash - prior.deployable_cash),
      count_delta: current.holdings_count - prior.holdings_count,
      equity_delta: round2(equityPct(current) - equityPct(prior)),
      aum_delta: prior.aum != null && current.aum != null ? round2(current.aum - prior.aum) : null,
    },
    changes: diffHoldings(prior, current),
    category_drift: categoryDrift(prior, current),
  };
}

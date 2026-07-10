"use client";
import { useEffect, useState } from "react";
import { useEmbedToken } from "@/hooks/use-embed-token";
import type { AmcSummary, FundSummary, AnalyseData, ChangesData } from "@/lib/types";

type View =
  | { kind: "amcs" }
  | { kind: "funds"; amc: string }
  | { kind: "periods"; amc: string; fund: FundSummary }
  | { kind: "fund"; amc: string; fund: FundSummary; period: string };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { ...(init?.headers ?? {}), "x-embed-token": token } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ error: res.statusText }))).error ?? res.statusText);
  return res.json() as Promise<T>;
}

function pct(n: number | null | undefined) {
  return n == null ? "—" : `${n.toFixed(2)}%`;
}

export default function HomePage() {
  const token = useEmbedToken();
  const [view, setView] = useState<View>({ kind: "amcs" });
  const [amcs, setAmcs] = useState<AmcSummary[] | null>(null);
  const [funds, setFunds] = useState<FundSummary[] | null>(null);
  const [periods, setPeriods] = useState<{ period: string }[] | null>(null);
  const [data, setData] = useState<ChangesData | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || view.kind !== "amcs") return;
    setError(null);
    api<AmcSummary[]>("/api/amcs", token).then(setAmcs).catch((e) => setError(String(e.message ?? e)));
  }, [token, view.kind]);

  useEffect(() => {
    if (!token || view.kind !== "funds") return;
    setError(null);
    api<FundSummary[]>(`/api/funds?amc=${view.amc}`, token).then(setFunds).catch((e) => setError(String(e.message ?? e)));
  }, [token, view]);

  useEffect(() => {
    if (!token || view.kind !== "periods") return;
    setError(null);
    api<{ period: string }[]>(`/api/periods?fund=${view.fund.amfi_code}`, token)
      .then(setPeriods)
      .catch((e) => setError(String(e.message ?? e)));
  }, [token, view]);

  useEffect(() => {
    if (!token || view.kind !== "fund") return;
    setError(null);
    setData(null);
    api<ChangesData>(`/api/changes?fund=${view.fund.amfi_code}&period=${view.period}`, token)
      .then(setData)
      .catch((e) => setError(String(e.message ?? e)));
  }, [token, view]);

  async function seed() {
    if (!token) return;
    setSeeding(true);
    try {
      const res = await api<Record<string, { inserted: number }>>("/api/admin/seed-ppfas", token, { method: "POST" });
      alert(`Seeded: ${Object.entries(res).map(([k, v]) => `${k}=${v.inserted}`).join(", ")}`);
      setAmcs(null);
      setView({ kind: "amcs" });
    } catch (e) {
      alert(`Seed failed: ${(e as Error).message}`);
    } finally {
      setSeeding(false);
    }
  }

  if (!token) {
    return <main className="min-h-[100dvh] flex items-center justify-center text-fg-secondary text-sm">Connecting…</main>;
  }

  return (
    <main className="min-h-[100dvh] max-w-screen-2xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs tracking-wide2 uppercase text-fg-secondary">MF Lookr</div>
          <h1 className="text-xl font-semibold text-fg-primary">Fund house → fund → year → month</h1>
        </div>
        <button
          onClick={seed}
          disabled={seeding}
          className="text-xs px-3 py-2 border border-line-default rounded-sm hover:bg-subtle disabled:opacity-50"
        >
          {seeding ? "Seeding…" : "Seed PPFAS (admin)"}
        </button>
      </header>

      {error && <div className="mb-4 text-sm text-error bg-tint-error border border-tint-error-border rounded-sm p-3">{error}</div>}

      <nav className="text-xs text-fg-secondary mb-4 flex gap-2 items-center">
        <button className="hover:text-fg-link" onClick={() => setView({ kind: "amcs" })}>Fund houses</button>
        {view.kind !== "amcs" && <span>/</span>}
        {"amc" in view && (
          <button className="hover:text-fg-link" onClick={() => setView({ kind: "funds", amc: view.amc })}>{view.amc}</button>
        )}
        {"fund" in view && <span>/ {view.fund.scheme_name}</span>}
        {view.kind === "fund" && <span>/ {view.period}</span>}
      </nav>

      {view.kind === "amcs" && (
        <ul className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {(amcs ?? []).map((a) => (
            <li key={a.slug}>
              <button
                className="w-full text-left border border-line-default rounded-sm p-4 hover:border-line-focus"
                onClick={() => setView({ kind: "funds", amc: a.slug })}
              >
                <div className="font-medium text-fg-primary">{a.name}</div>
                <div className="text-xs text-fg-secondary mt-1">{a.fund_count} funds · {a.status}</div>
              </button>
            </li>
          ))}
          {amcs && amcs.length === 0 && <li className="text-sm text-fg-secondary">No fund houses loaded yet — use "Seed PPFAS" above.</li>}
        </ul>
      )}

      {view.kind === "funds" && (
        <ul className="flex flex-col gap-2">
          {(funds ?? []).map((f) => (
            <li key={f.amfi_code}>
              <button
                className="w-full text-left border border-line-default rounded-sm p-3 hover:border-line-focus flex justify-between items-center"
                onClick={() => setView({ kind: "periods", amc: view.amc, fund: f })}
              >
                <span className="text-fg-primary text-sm">{f.scheme_name}</span>
                <span className="text-xs text-fg-secondary">{f.category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {view.kind === "periods" && (
        <ul className="flex flex-wrap gap-2">
          {(periods ?? []).map((p) => (
            <li key={p.period}>
              <button
                className="border border-line-default rounded-sm px-3 py-2 text-sm hover:border-line-focus"
                onClick={() => setView({ kind: "fund", amc: view.amc, fund: view.fund, period: p.period })}
              >
                {p.period}
              </button>
            </li>
          ))}
        </ul>
      )}

      {view.kind === "fund" && data && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Kpi label="AUM (₹ cr)" value={data.current.aum?.toLocaleString() ?? "—"} />
            <Kpi label="Holdings" value={String(data.current.holdings_count)} />
            <Kpi label="Deployable cash" value={pct(data.current.deployable_cash)} />
            <Kpi label="Total weight" value={pct(data.current.total_weight)} />
          </div>

          <section>
            <h2 className="text-xs tracking-wide2 uppercase text-fg-secondary mb-2">Asset allocation</h2>
            <div className="flex gap-2 flex-wrap">
              {data.current.asset_allocation.map((a) => (
                <div key={a.name} className="border border-line-subtle rounded-sm px-3 py-2 text-sm">
                  {a.name}: <span className="font-medium">{pct(a.weight)}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-xs tracking-wide2 uppercase text-fg-secondary mb-2">Top holdings</h2>
            <table className="w-full text-sm">
              <tbody>
                {data.current.top_holdings.map((h) => (
                  <tr key={h.name} className="border-b border-line-subtle">
                    <td className="py-1.5 pr-3">{h.name}</td>
                    <td className="py-1.5 pr-3 text-fg-secondary">{h.sector}</td>
                    <td className="py-1.5 text-right font-mono">{pct(h.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {data.previous ? (
            <section>
              <h2 className="text-xs tracking-wide2 uppercase text-fg-secondary mb-2">
                Changes vs {data.previous.period}
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <Kpi label="Cash Δ" value={pct(data.kpis?.cash_delta)} />
                <Kpi label="Equity Δ" value={pct(data.kpis?.equity_delta)} />
                <Kpi label="Count Δ" value={String(data.kpis?.count_delta ?? "—")} />
                <Kpi label="AUM Δ (₹cr)" value={data.kpis?.aum_delta?.toLocaleString() ?? "—"} />
              </div>
              <ChangeList title="Added" rows={data.changes?.added ?? []} />
              <ChangeList title="Exited" rows={data.changes?.exited ?? []} />
              <ChangeList title="Increased" rows={data.changes?.increased ?? []} />
              <ChangeList title="Reduced" rows={data.changes?.reduced ?? []} />
            </section>
          ) : (
            <div className="text-sm text-fg-secondary">No prior month stored yet for this fund — changes will show once a second month is loaded.</div>
          )}

          <section>
            <h2 className="text-xs tracking-wide2 uppercase text-fg-secondary mb-2">
              All holdings ({data.current.holdings.length})
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-fg-secondary border-b border-line-default">
                  <th className="py-1.5 font-normal">Name</th>
                  <th className="py-1.5 font-normal">Type</th>
                  <th className="py-1.5 font-normal">Sector / rating</th>
                  <th className="py-1.5 font-normal text-right">Weight</th>
                </tr>
              </thead>
              <tbody>
                {[...data.current.holdings].sort((a, b) => b.weight - a.weight).map((h, i) => (
                  <tr key={`${h.name}-${i}`} className="border-b border-line-subtle">
                    <td className="py-1.5 pr-3">{h.name}</td>
                    <td className="py-1.5 pr-3 text-fg-secondary">{h.instrument_type}</td>
                    <td className="py-1.5 pr-3 text-fg-secondary">{h.sector}</td>
                    <td className="py-1.5 text-right font-mono">{pct(h.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </main>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-line-subtle rounded-sm p-3">
      <div className="text-xs text-fg-secondary">{label}</div>
      <div className="text-lg font-semibold text-fg-primary font-mono">{value}</div>
    </div>
  );
}

function ChangeList({ title, rows }: { title: string; rows: { name: string; delta: number; weight_b: number }[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="mb-3">
      <div className="text-xs font-medium text-fg-secondary mb-1">{title} ({rows.length})</div>
      <ul className="text-sm flex flex-col gap-0.5">
        {rows.slice(0, 15).map((r) => (
          <li key={r.name} className="flex justify-between border-b border-line-subtle py-1">
            <span>{r.name}</span>
            <span className={`font-mono ${r.delta >= 0 ? "text-success" : "text-error"}`}>
              {r.delta >= 0 ? "+" : ""}{r.delta.toFixed(2)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

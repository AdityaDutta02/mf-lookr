// AI narrative for a fund/period — the structural fix for the old app's broken
// insight route (mf-analyser/app/api/ai/insight/route.ts), which only ever saw
// a single month's snapshot and so could describe a portfolio but never a
// *change* in one. This route feeds the model the already-computed
// month-over-month diff (added/exited/increased/reduced quantity deltas,
// category drift, KPI deltas) from lib/changes.ts — the same deterministic
// computation /api/changes uses — and asks it only to narrate those numbers,
// never to compute or invent any of its own.
import { NextRequest, NextResponse } from "next/server";
import { callGateway } from "@/lib/terminal-ai";
import { dbInsert, dbList } from "@/lib/db";
import { buildChangesData } from "@/lib/changes";
import type { AIInsight, AnalyseData, ChangesData } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface DisclosureRow {
  amfi_code: string;
  period: string;
  data: AnalyseData;
}

interface AiCacheRow {
  amfi_code: string;
  period: string;
  insight: AIInsight;
}

// Tone/constraints carried over from mf-analyser/app/api/ai/insight/route.ts's
// SYSTEM prompt (descriptive-not-advisory framing) — what changed is WHAT gets
// fed in: a computed month-over-month diff instead of one month's snapshot.
const SYSTEM = `You are a buy-side research analyst writing a concise, factual interpretation of a mutual fund's monthly portfolio, focused on what changed since the prior month.
RULES:
- Be descriptive and analytical, NEVER advisory. Do not recommend buying, selling, holding, or rate the fund.
- Use ONLY the numbers provided in the input JSON. Never invent, estimate, or restate a number that isn't already present in the input — every % and figure you mention must come directly from the payload.
- The input's "changes" lists holdings bucketed by added/exited/increased/reduced SHARE QUANTITY (not price-driven weight drift) — narrate position changes in terms of what's given (names, quantity_delta_pct where present), never invent a rupee or unit figure not given.
- If "previous" is null, there is no prior month to compare against — describe only the current snapshot (concentration, cash, category mix) and add a flag noting no month-over-month comparison is available yet. Do not describe anything as "increased" or "decreased" in that case.
- Output STRICT JSON only (no markdown, no prose outside JSON) matching exactly:
{"headline": string, "sections": [{"title": string, "bullets": [string, ...]}], "flags": [string, ...]}
- 1 headline sentence; 2-3 sections (e.g. "Portfolio posture", "Notable position changes", "Category drift & cash"); 2-4 bullets each; 1-3 flags noting risks visible in the data (e.g. elevated cash, single-name concentration, large exits). Keep it grounded and specific to the numbers given.`;

function compact(cd: ChangesData) {
  const d = cd.current;
  return {
    scheme_name: d.scheme_name,
    category: d.category,
    asset_class: d.asset_class,
    period_label: d.period_label,
    aum_cr: d.aum,
    holdings_count: d.holdings_count,
    deployable_cash_pct: d.deployable_cash,
    total_weight: d.total_weight,
    asset_allocation: d.asset_allocation,
    top_holdings: d.top_holdings.slice(0, 10),
    previous: cd.previous
      ? { period_label: cd.previous.period_label }
      : null,
    kpis: cd.kpis,
    category_drift: cd.category_drift,
    changes: cd.changes
      ? {
          added: cd.changes.added.slice(0, 15).map((r) => ({ name: r.name, quantity_delta_pct: r.quantity_delta_pct })),
          exited: cd.changes.exited.slice(0, 15).map((r) => ({ name: r.name })),
          increased: cd.changes.increased.slice(0, 15).map((r) => ({ name: r.name, quantity_delta_pct: r.quantity_delta_pct })),
          reduced: cd.changes.reduced.slice(0, 15).map((r) => ({ name: r.name, quantity_delta_pct: r.quantity_delta_pct })),
        }
      : null,
  };
}

function parseInsight(content: string): AIInsight | null {
  let txt = content.trim();
  const fence = txt.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) txt = fence[1].trim();
  const start = txt.indexOf("{");
  const end = txt.lastIndexOf("}");
  if (start === -1 || end === -1) return null;
  try {
    const obj = JSON.parse(txt.slice(start, end + 1)) as Partial<AIInsight>;
    if (!obj.headline || !Array.isArray(obj.sections)) return null;
    return {
      generated_at: new Date().toISOString(),
      headline: String(obj.headline),
      sections: obj.sections.map((s) => ({ title: String(s.title), bullets: (s.bullets ?? []).map(String) })),
      flags: Array.isArray(obj.flags) ? obj.flags.map(String) : [],
    };
  } catch {
    return null;
  }
}

export async function POST(req: NextRequest) {
  const token = req.headers.get("x-embed-token");
  const body = (await req.json().catch(() => ({}))) as { fund?: string; period?: string };
  const fund = body.fund ?? "";
  const period = body.period ?? "";
  if (!token || !fund || !period) {
    return NextResponse.json({ error: "missing token/fund/period" }, { status: 400 });
  }

  // Cache hit?
  try {
    const cached = await dbList<AiCacheRow>("ai_cache", { amfi_code: fund, period }, token);
    const hit = cached.find((c) => c.period === period);
    if (hit?.insight?.headline) return NextResponse.json(hit.insight);
  } catch {
    /* ignore — fall through to generation */
  }

  let changesData: ChangesData;
  try {
    const rows = await dbList<DisclosureRow>("disclosures", { amfi_code: fund }, token);
    const current = rows.find((r) => r.period === period);
    if (!current) return NextResponse.json({ error: "no disclosure for that fund/period" }, { status: 404 });
    const prior = rows.filter((r) => r.period < period).sort((a, b) => (a.period < b.period ? 1 : -1))[0];
    changesData = buildChangesData(current.data, prior ? prior.data : null);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  try {
    const result = await callGateway(
      [{ role: "user", content: `Interpret this fund's portfolio and month-over-month change. Input JSON:\n${JSON.stringify(compact(changesData))}` }],
      token,
      { category: "chat", tier: "good", system: SYSTEM },
    );
    const insight = parseInsight(result.content);
    if (!insight) return NextResponse.json({ error: "could not parse interpretation" }, { status: 502 });
    try {
      await dbInsert("ai_cache", { amfi_code: fund, period, insight }, token);
    } catch {
      /* best-effort cache — a unique_violation on race just means another
         request already wrote it, which is fine */
    }
    return NextResponse.json(insight);
  } catch (e) {
    const err = e as Error & { code?: string; redirect?: string };
    if (err.code === "INSUFFICIENT_CREDITS") {
      return NextResponse.json({ error: err.message, code: "INSUFFICIENT_CREDITS", redirect: err.redirect }, { status: 402 });
    }
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

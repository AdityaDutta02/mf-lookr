// Month-over-month changes for a fund, auto-resolving the prior stored period
// server-side (no manual A/B like the old app's /api/compare — that's what made
// the old changes panel fragile: it required the caller to already know which
// two periods to diff). Keys diffs on ISIN when present, falling back to
// normalized name — PPFAS's factsheet discloses no ISIN at all, so its diffs
// are name-keyed, same fallback the old app used, just always taken here.
//
// Diff logic lives in lib/changes.ts so app/api/ai/insight/route.ts can reuse
// the exact same computation rather than duplicating it or round-tripping HTTP.
import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";
import { buildChangesData } from "@/lib/changes";
import type { AnalyseData, ChangesData } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface DisclosureRow {
  amfi_code: string;
  period: string;
  data: AnalyseData;
}

export async function GET(req: NextRequest) {
  const fund = req.nextUrl.searchParams.get("fund") ?? "";
  const period = req.nextUrl.searchParams.get("period") ?? "";
  const token = req.headers.get("x-embed-token") ?? "";
  if (!fund || !period) return NextResponse.json({ error: "fund and period are required" }, { status: 400 });

  try {
    const rows = await dbList<DisclosureRow>("disclosures", { amfi_code: fund }, token);
    const current = rows.find((r) => r.period === period);
    if (!current) return NextResponse.json({ error: "no disclosure for that fund/period" }, { status: 404 });

    const prior = rows
      .filter((r) => r.period < period)
      .sort((a, b) => (a.period < b.period ? 1 : -1))[0];

    const payload: ChangesData = buildChangesData(current.data, prior ? prior.data : null);
    return NextResponse.json(payload);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

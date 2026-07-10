import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";
import type { AnalyseData } from "@/lib/types";

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
    const rows = await dbList<DisclosureRow>("disclosures", { amfi_code: fund, period }, token);
    if (rows.length === 0) return NextResponse.json({ error: "no disclosure for that fund/period" }, { status: 404 });
    return NextResponse.json(rows[0].data);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

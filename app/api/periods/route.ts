import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface DisclosureRow {
  period: string;
  year: number;
  month: number;
}

export async function GET(req: NextRequest) {
  const fund = req.nextUrl.searchParams.get("fund") ?? "";
  const token = req.headers.get("x-embed-token") ?? "";
  if (!fund) return NextResponse.json({ error: "fund (amfi_code) is required" }, { status: 400 });
  try {
    const rows = await dbList<DisclosureRow>("disclosures", { amfi_code: fund }, token);
    const periods = rows
      .map((r) => ({ period: r.period, year: r.year, month: r.month }))
      .sort((a, b) => (a.period < b.period ? 1 : -1));
    return NextResponse.json(periods);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

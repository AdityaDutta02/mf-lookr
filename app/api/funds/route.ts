import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";
import type { FundSummary } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const amc = req.nextUrl.searchParams.get("amc") ?? "";
  const token = req.headers.get("x-embed-token") ?? "";
  if (!amc) return NextResponse.json({ error: "amc is required" }, { status: 400 });
  try {
    const funds = await dbList<FundSummary>("funds", { amc_slug: amc }, token);
    return NextResponse.json(funds);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

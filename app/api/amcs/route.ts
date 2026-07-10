import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface AmcRow {
  slug: string;
  name: string;
  status: string;
}
interface FundRow {
  amc_slug: string;
}

export async function GET(req: NextRequest) {
  const token = req.headers.get("x-embed-token") ?? "";
  try {
    const [amcs, funds] = await Promise.all([
      dbList<AmcRow>("amcs", {}, token),
      dbList<FundRow>("funds", {}, token),
    ]);
    const counts = new Map<string, number>();
    for (const f of funds) counts.set(f.amc_slug, (counts.get(f.amc_slug) ?? 0) + 1);
    const out = amcs.map((a) => ({ slug: a.slug, name: a.name, status: a.status, fund_count: counts.get(a.slug) ?? 0 }));
    return NextResponse.json(out);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

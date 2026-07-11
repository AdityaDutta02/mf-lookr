// Live NAV — decoupled from any stored disclosure period. AMFI publishes one
// flat text file with every scheme's latest NAV, updated once per business
// day (see tools/cache/amfi_nav.txt for the cached format this mirrors):
// "Scheme Code;ISIN Growth;ISIN Reinvest;Scheme Name;Net Asset Value;Date"
// We fetch it fresh (Next's fetch cache handles the revalidate window — no
// point re-downloading a ~1MB file on every request when the source itself
// only changes once a day) and pull the row for the requested AMFI code.
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt";
const REVALIDATE_SECONDS = 3600; // NAV only changes once/day — hourly is plenty fresh

export async function GET(req: NextRequest) {
  const fund = req.nextUrl.searchParams.get("fund") ?? "";
  if (!fund) return NextResponse.json({ error: "fund (amfi_code) is required" }, { status: 400 });

  let text: string;
  try {
    const res = await fetch(AMFI_URL, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) throw new Error(`AMFI feed returned ${res.status}`);
    text = await res.text();
  } catch (e) {
    return NextResponse.json({ error: `Could not reach AMFI's NAV feed: ${(e as Error).message}` }, { status: 502 });
  }

  for (const line of text.split("\n")) {
    const cols = line.split(";");
    if (cols.length < 6) continue;
    if (cols[0].trim() !== fund) continue;
    const nav = parseFloat(cols[4].trim());
    const date = cols[5].trim();
    if (!Number.isFinite(nav)) continue;
    return NextResponse.json({ amfi_code: fund, nav, date });
  }

  return NextResponse.json({ error: `No NAV found for scheme code ${fund}` }, { status: 404 });
}

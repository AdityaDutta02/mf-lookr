// Full-corpus fund search — GET ?q=<query>. Case-insensitive substring match
// on scheme_name / amc_name / category, capped at 25 results. Debounce is a
// frontend concern (SearchView.tsx); this route just does a bounded query.
import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";
import type { FundSummary, SchemeMatch, SearchResult } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface AmcRow {
  slug: string;
  name: string;
}

const MAX_RESULTS = 25;

export async function GET(req: NextRequest) {
  const q = (req.nextUrl.searchParams.get("q") ?? "").trim();
  const token = req.headers.get("x-embed-token") ?? "";
  if (!q) return NextResponse.json({ type: "empty" } satisfies SearchResult);

  try {
    const [funds, amcs] = await Promise.all([
      dbList<FundSummary>("funds", {}, token),
      dbList<AmcRow>("amcs", {}, token),
    ]);
    const amcNameOf = new Map(amcs.map((a) => [a.slug, a.name]));
    const needle = q.toLowerCase();

    const matches: SchemeMatch[] = [];
    for (const f of funds) {
      const amcName = amcNameOf.get(f.amc_slug) ?? f.amc_slug;
      const haystack = `${f.scheme_name} ${amcName} ${f.category ?? ""}`.toLowerCase();
      if (!haystack.includes(needle)) continue;
      matches.push({
        amfi_code: f.amfi_code,
        scheme_name: f.scheme_name,
        amc_name: amcName,
        amc_slug: f.amc_slug,
        category: f.category,
        asset_class: f.asset_class,
      });
      if (matches.length >= MAX_RESULTS) break;
    }

    if (matches.length === 0) return NextResponse.json({ type: "empty" } satisfies SearchResult);
    return NextResponse.json({ type: "name", schemes: matches } satisfies SearchResult);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

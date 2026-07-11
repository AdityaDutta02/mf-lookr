// One-shot bootstrap: inserts the locally-parsed Navi bundle (built by
// tools/build_dataset_navi.py from the local extraction toolkit — see
// tools/discover_navi_xlsx.py / parse_navi_xlsx.py) into amcs/funds/disclosures
// via the gateway. Mirrors app/api/admin/seed-ppfas/route.ts exactly.
//
// disclosures are fully SCRUBBED (delete every existing amc_slug: "navi" row,
// then insert fresh) on every run — same full-wipe-and-reload rationale as
// seed-ppfas's route (a partial "only delete matching keys" replace leaves
// room for stale rows to survive a re-run). This route ONLY ever touches rows
// with amc_slug: "navi" — the dbList/dbDelete scrub loop below is filtered to
// {amc_slug: "navi"} and nothing else, so it can never reach ppfas/hdfc/axis/
// invesco/sbi/nippon/etc rows other agents are loading in parallel in this
// same repo. amcs/funds are stable identity data — plain dbBulkInsert is fine
// there, a unique_violation on re-run means "already correct."
import { NextRequest, NextResponse } from "next/server";
import { dbBulkInsert, dbDelete, dbList } from "@/lib/db";
import { loadBundle } from "@/lib/seed-data";

// Supports either a single data.json or chunked data-0.json, data-1.json,
// ... (see tools/split_bundle.py) — full-history bundles can exceed
// GitHub's hard 100MB-per-file cap as a single file.
const bundle = loadBundle("seed-navi");

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface DisclosureRow {
  id: string;
  amfi_code: string;
  period: string;
}

export async function POST(req: NextRequest) {
  const token = req.headers.get("x-embed-token");
  if (!token) return NextResponse.json({ error: "missing embed token" }, { status: 401 });

  try {
    const amcResult = await dbBulkInsert("amcs", bundle.amcs, token);
    const fundResult = await dbBulkInsert("funds", bundle.funds, token);

    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: "navi" }, token);
    for (const row of existing) {
      await dbDelete("disclosures", row.id, token);
    }

    const disclosureResult = await dbBulkInsert("disclosures", bundle.disclosures, token);

    return NextResponse.json({
      amcs: { inserted: amcResult.inserted.length, errors: amcResult.errors },
      funds: { inserted: fundResult.inserted.length, errors: fundResult.errors },
      disclosures_scrubbed: existing.length,
      disclosures: { inserted: disclosureResult.inserted.length, errors: disclosureResult.errors },
    });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

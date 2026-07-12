// One-shot bootstrap: inserts the locally-parsed PPFAS bundle (built by
// tools/build_dataset.py from the local extraction toolkit — see tools/README.md)
// into amcs/funds/disclosures via the gateway.
//
// disclosures are fully SCRUBBED (delete every existing ppfas row, then insert fresh)
// on every run, not just replaced for the periods this bundle happens to cover. A
// partial "only delete matching keys" replace was tried first and left room for stale
// rows to survive a re-run (e.g. from an earlier bundle that covered different
// periods, or a parser change that renamed a fund) — full scrub removes that risk
// entirely. amcs/funds are stable identity data — plain dbBulkInsert is fine there,
// a unique_violation on re-run means "already correct."
import { NextRequest, NextResponse } from "next/server";
import { dbDelete, dbList } from "@/lib/db";
import { bulkInsertChunked } from "@/lib/seed-bulk";
import { loadBundle } from "@/lib/seed-data";

// Supports either a single data.json or chunked data-0.json, data-1.json,
// ... (see tools/split_bundle.py) — full-history bundles can exceed
// GitHub's hard 100MB-per-file cap as a single file.
const bundle = loadBundle("seed-ppfas");

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
    const amcResult = await bulkInsertChunked("amcs", bundle.amcs, token);
    const fundResult = await bulkInsertChunked("funds", bundle.funds, token);

    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: "ppfas" }, token);
    for (const row of existing) {
      await dbDelete("disclosures", row.id, token);
    }

    const disclosureResult = await bulkInsertChunked("disclosures", bundle.disclosures, token);

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

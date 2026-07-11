// One-shot bootstrap: inserts the locally-parsed Motilal Oswal bundle (built by
// tools/build_dataset_motilal.py from the local extraction toolkit — see
// tools/README.md) into amcs/funds/disclosures via the gateway. Mirrors
// app/api/admin/seed-ppfas/route.ts exactly.
//
// HARD-SCOPED to amc_slug: "motilal" ONLY — every read/delete/insert below is
// filtered to "motilal". This route must never touch ppfas/hdfc/axis/invesco/
// sbi/nippon/navi/etc rows, which other agents are loading into this same
// table concurrently.
//
// disclosures are fully SCRUBBED (delete every existing motilal row, then
// insert fresh) on every run, not just replaced for the periods this bundle
// happens to cover — see seed-ppfas/route.ts's comment for why partial
// replace leaves stale rows behind. amcs/funds are stable identity data —
// plain dbBulkInsert is fine there, a unique_violation on re-run means
// "already correct."
import { NextRequest, NextResponse } from "next/server";
import { dbDelete, dbList } from "@/lib/db";
import { bulkInsertChunked } from "@/lib/seed-bulk";
import { loadBundle } from "@/lib/seed-data";

// Supports either a single data.json or chunked data-0.json, data-1.json,
// ... (see tools/split_bundle.py) — full-history bundles can exceed
// GitHub's hard 100MB-per-file cap as a single file.
const bundle = loadBundle("seed-motilal");

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AMC_SLUG = "motilal";

interface DisclosureRow {
  id: string;
  amfi_code: string;
  period: string;
}

export async function POST(req: NextRequest) {
  const token = req.headers.get("x-embed-token");
  if (!token) return NextResponse.json({ error: "missing embed token" }, { status: 401 });

  // Defense in depth: refuse to run if the bundled data ever drifts from the
  // amc_slug this route is allowed to touch. `amcs` rows key their AMC
  // identity as `slug`, not `amc_slug` (that field only exists on `funds`/
  // `disclosures` rows) — checking all three arrays for `amc_slug` was a bug
  // that made every `amcs` row a false positive, since it has no such field.
  const offendingAmc = bundle.amcs.find((row) => (row as { slug?: string }).slug !== AMC_SLUG);
  const offendingFundOrDisclosure = [...bundle.funds, ...bundle.disclosures].find(
    (row) => (row as { amc_slug?: string }).amc_slug !== AMC_SLUG,
  );
  if (offendingAmc || offendingFundOrDisclosure) {
    return NextResponse.json(
      { error: `bundle contains a row not scoped to amc_slug "${AMC_SLUG}"` },
      { status: 500 },
    );
  }

  try {
    const amcResult = await bulkInsertChunked("amcs", bundle.amcs, token);
    const fundResult = await bulkInsertChunked("funds", bundle.funds, token);

    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: AMC_SLUG }, token);
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

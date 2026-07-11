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
import { dbBulkInsert, dbDelete, dbList } from "@/lib/db";
import fs from "node:fs";
import path from "node:path";

// Read at request time rather than `import bundle from "./data.json"` — a
// static import makes TypeScript infer a giant literal type from the JSON's
// full content, which OOMs the type-checker once several fund houses' large
// bundles (30-60MB each) are all statically imported at once across the
// seed-* routes. A runtime read sidesteps that entirely.
interface Bundle {
  amcs: Record<string, unknown>[];
  funds: Record<string, unknown>[];
  disclosures: Record<string, unknown>[];
}
const bundle: Bundle = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "app/api/admin/seed-motilal/data.json"), "utf8")
);

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
  // amc_slug this route is allowed to touch.
  const offending = [...bundle.amcs, ...bundle.funds, ...bundle.disclosures].find(
    (row) => (row as { amc_slug?: string }).amc_slug !== AMC_SLUG,
  );
  if (offending) {
    return NextResponse.json(
      { error: `bundle contains a row not scoped to amc_slug "${AMC_SLUG}"` },
      { status: 500 },
    );
  }

  try {
    const amcResult = await dbBulkInsert("amcs", bundle.amcs, token);
    const fundResult = await dbBulkInsert("funds", bundle.funds, token);

    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: AMC_SLUG }, token);
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

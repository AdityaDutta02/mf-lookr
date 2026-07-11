// One-shot bootstrap: inserts the locally-parsed SBI bundle (built by
// tools/build_dataset_sbi.py — see tools/README.md) into amcs/funds/disclosures
// via the gateway. Mirrors app/api/admin/seed-hdfc/route.ts's pattern EXACTLY —
// full scrub-then-reload — but every read/delete/insert below is hard-scoped to
// amc_slug: "sbi" only. This is a locked constraint: an SBI seed run must never
// touch a ppfas/hdfc/other-AMC-slugged row. Compare the dbList/dbDelete calls
// here against seed-hdfc/route.ts's — same shape, only the slug differs.
//
// disclosures are fully SCRUBBED (delete every existing sbi row, then insert
// fresh) on every run, not just replaced for the periods this bundle happens to
// cover — see seed-ppfas/route.ts's comment for why a partial replace isn't safe.
// amcs/funds are stable identity data — plain dbBulkInsert is fine there, a
// unique_violation on re-run means "already correct."
import { NextRequest, NextResponse } from "next/server";
import { dbDelete, dbList } from "@/lib/db";
import { bulkInsertChunked } from "@/lib/seed-bulk";
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
  fs.readFileSync(path.join(process.cwd(), "app/api/admin/seed-sbi/data.json"), "utf8")
);

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

    // Hard-scoped to amc_slug: "sbi" — must never read/delete a non-sbi-slugged row.
    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: "sbi" }, token);
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

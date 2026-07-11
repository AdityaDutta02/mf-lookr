// One-shot bootstrap: inserts the locally-parsed PPFAS bundle (built by
// tools/build_dataset.py from the local extraction toolkit — see tools/README.md)
// into amcs/funds/disclosures via the gateway.
//
// disclosures are REPLACED (delete-then-insert) for any (amfi_code, period) this
// bundle covers, not just inserted — a re-run must be able to overwrite stale data
// (e.g. this app's first seed used the factsheet-PDF parser, which has no ISIN/
// quantity; re-seeding from the XLS parser needs to actually replace those rows,
// not silently no-op on the unique constraint). amcs/funds are stable identity
// data — plain dbBulkInsert is fine there, a unique_violation on re-run means
// "already correct."
import { NextRequest, NextResponse } from "next/server";
import { dbBulkInsert, dbDelete, dbList } from "@/lib/db";
import bundle from "./data.json";

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

    const targetKeys = new Set(bundle.disclosures.map((d) => `${d.amfi_code}|${d.period}`));
    const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: "ppfas" }, token);
    const toDelete = existing.filter((r) => targetKeys.has(`${r.amfi_code}|${r.period}`));
    for (const row of toDelete) {
      await dbDelete("disclosures", row.id, token);
    }

    const disclosureResult = await dbBulkInsert("disclosures", bundle.disclosures, token);

    return NextResponse.json({
      amcs: { inserted: amcResult.inserted.length, errors: amcResult.errors },
      funds: { inserted: fundResult.inserted.length, errors: fundResult.errors },
      disclosures_replaced: toDelete.length,
      disclosures: { inserted: disclosureResult.inserted.length, errors: disclosureResult.errors },
    });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

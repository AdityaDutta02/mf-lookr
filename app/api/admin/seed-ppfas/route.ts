// One-shot bootstrap: inserts the locally-parsed PPFAS bundle (built by
// tools/build_dataset.py from the local extraction toolkit — see tools/README.md)
// into amcs/funds/disclosures via the gateway. Idempotent: dbBulkInsert reports
// unique_violation per-row on a re-run, which is safe to ignore (already written).
import { NextRequest, NextResponse } from "next/server";
import { dbBulkInsert } from "@/lib/db";
import bundle from "./data.json";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const token = req.headers.get("x-embed-token");
  if (!token) return NextResponse.json({ error: "missing embed token" }, { status: 401 });

  try {
    const amcResult = await dbBulkInsert("amcs", bundle.amcs, token);
    const fundResult = await dbBulkInsert("funds", bundle.funds, token);

    const disclosureResult = await dbBulkInsert("disclosures", bundle.disclosures, token);

    return NextResponse.json({
      amcs: { inserted: amcResult.inserted.length, errors: amcResult.errors },
      funds: { inserted: fundResult.inserted.length, errors: fundResult.errors },
      disclosures: { inserted: disclosureResult.inserted.length, errors: disclosureResult.errors },
    });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

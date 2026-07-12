// Shared handler behind every app/api/admin/seed-<amc>/route.ts's POST.
//
// The old shape did the ENTIRE scrub-then-reload (delete every existing row,
// insert the whole bundle) inside one HTTP request. That works for a small
// AMC but not once a fund house has a full-history backfill: HDFC's ~1000+
// existing rows to delete plus ~5000 disclosures to insert took long enough,
// even paced, that the platform gateway's own reverse-proxy timeout killed
// the connection with a 502 before the route could ever finish and respond
// — the work was succeeding server-side, there was just no way to report
// it back over the timed-out connection.
//
// Fix: break the operation into small, fast, independently-callable steps,
// and let the CLIENT drive the loop (see app/page.tsx's seed()) — each HTTP
// call does at most a few hundred rows and returns in well under a second,
// so no single request is ever at risk of the gateway's timeout, no matter
// how large the AMC's full history is.
//
// Every action here is still hard-scoped to the ONE amc_slug baked into the
// calling route.ts (via its own bundle + AMC_SLUG constant) — the action
// name/body never lets a caller target a different AMC's rows. `ids` in
// delete-batch are only ever ones this same route's own list-existing step
// just handed back (itself filtered by amc_slug server-side), so this is a
// pagination cursor, not client-controlled scope.
import { NextRequest, NextResponse } from "next/server";
import { dbList } from "@/lib/db";
import { bulkInsertChunked, deleteAllChunked } from "@/lib/seed-bulk";
import type { Bundle } from "@/lib/seed-data";

interface DisclosureRow {
  id: string;
  amfi_code: string;
  period: string;
}

const DISCLOSURE_INSERT_BATCH = 300; // small enough that one gateway call (or two) always finishes fast
const DELETE_BATCH_MAX = 50; // defensive cap — a coding bug shouldn't be able to fire an unbounded delete

export async function handleSeedAction(req: NextRequest, amcSlug: string, bundle: Bundle): Promise<NextResponse> {
  const token = req.headers.get("x-embed-token");
  if (!token) return NextResponse.json({ error: "missing embed token" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as {
    action?: string;
    ids?: string[];
    offset?: number;
  };

  try {
    switch (body.action) {
      case "list-existing": {
        const existing = await dbList<DisclosureRow>("disclosures", { amc_slug: amcSlug }, token);
        return NextResponse.json({ ids: existing.map((r) => r.id) });
      }

      case "delete-batch": {
        const ids = (body.ids ?? []).slice(0, DELETE_BATCH_MAX);
        await deleteAllChunked("disclosures", ids, token);
        return NextResponse.json({ deleted: ids.length });
      }

      case "insert-identity": {
        const amcResult = await bulkInsertChunked("amcs", bundle.amcs, token);
        const fundResult = await bulkInsertChunked("funds", bundle.funds, token);
        return NextResponse.json({
          amcs: { inserted: amcResult.inserted.length, errors: amcResult.errors },
          funds: { inserted: fundResult.inserted.length, errors: fundResult.errors },
        });
      }

      case "insert-disclosures-batch": {
        const offset = body.offset ?? 0;
        const slice = bundle.disclosures.slice(offset, offset + DISCLOSURE_INSERT_BATCH);
        const result = await bulkInsertChunked("disclosures", slice, token);
        const nextOffset = offset + slice.length;
        return NextResponse.json({
          inserted: result.inserted.length,
          errors: result.errors,
          nextOffset,
          total: bundle.disclosures.length,
          done: nextOffset >= bundle.disclosures.length,
        });
      }

      default:
        return NextResponse.json({ error: `unknown or missing action: ${body.action}` }, { status: 400 });
    }
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}

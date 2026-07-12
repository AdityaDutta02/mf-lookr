// One-shot bootstrap: inserts the locally-parsed ICICI Prudential bundle into
// amcs/funds/disclosures via the gateway. Hard-scoped to amc_slug: "icici"
// only — must never read/delete/insert a differently-slugged row. Seeding is
// driven step-by-step by the client (see app/page.tsx's seed()) rather than
// one big request — see lib/seed-actions.ts for why and the shared handler.
import { NextRequest } from "next/server";
import { handleSeedAction } from "@/lib/seed-actions";
import { loadBundle } from "@/lib/seed-data";

const AMC_SLUG = "icici";
const bundle = loadBundle("seed-icici");

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  return handleSeedAction(req, AMC_SLUG, bundle);
}

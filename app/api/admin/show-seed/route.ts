// Whether the seed admin controls should render. Deliberately a plain
// server-only env var (no NEXT_PUBLIC_ prefix) read at REQUEST time, not a
// build-time constant — NEXT_PUBLIC_* vars get inlined into the client bundle
// during `npm run build`, but this app's Dockerfile builds in a stage that
// never receives the platform's set_env_var values as Docker build args
// (only the runtime container gets them). A build-time flag could therefore
// never be flipped by set_env_var + redeploy alone. This route reads the
// container's live env on every request instead, so toggling SHOW_SEED and
// redeploying (container restart, no rebuild needed) actually works.
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ showSeed: process.env.SHOW_SEED === "1" });
}

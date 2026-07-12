// Shared by every app/api/admin/seed-<amc>/route.ts. A fixed row-count chunk
// (e.g. 900 rows/call) isn't a safe proxy for request-body size — disclosure
// rows carry a full holdings JSONB blob whose size varies a lot per fund
// (index funds: a handful of holdings; large equity/hybrid funds: 100+), so
// a 900-row chunk can be ~8MB for one AMC and ~15MB+ for another. Several
// fund houses (HDFC, Nippon, Mirae, ICICI) hit "request body too large" at a
// flat 900-row chunk size while others (SBI, Invesco) didn't, purely because
// of average row size — so chunk by actual JSON byte size instead, with the
// row-count cap kept only as a secondary guard against dbBulkInsert's own
// 1000-row/call limit (see lib/db.ts).
import { dbBulkInsert, dbDelete } from "@/lib/db";

const MAX_CHUNK_BYTES = 2_000_000; // conservative margin under the gateway's body-size cap
const MAX_CHUNK_ROWS = 900; // stay under dbBulkInsert's hard 1000-row/call cap

// There's no bulk-delete endpoint (only POST /db/<table>/bulk for inserts —
// see lib/db.ts), so scrubbing existing rows before a reseed means one
// dbDelete call per row. Doing that fully sequentially (one row, wait, next
// row) meant HDFC's ~1000+ existing rows took minutes of wall time — long
// enough that the platform gateway/browser dropped the connection
// ("Failed to fetch") well before the route finished, even though the
// deletes themselves were succeeding server-side. Fire them in small
// concurrent batches instead, PACED to stay under the gateway's 600
// calls/min (=10/sec) budget — firing a batch as fast as each Promise.all
// resolves (often well under 1s round-trip) can burst past that cap and
// draw 429s that exhaust dbDelete's own retry budget, so each batch is
// floored to a minimum 1100ms cadence regardless of how fast it finishes.
const DELETE_BATCH_SIZE = 8;
const DELETE_BATCH_MIN_MS = 1100;

export async function deleteAllChunked(table: string, ids: string[], token: string): Promise<void> {
  for (let i = 0; i < ids.length; i += DELETE_BATCH_SIZE) {
    const batch = ids.slice(i, i + DELETE_BATCH_SIZE);
    const started = Date.now();
    await Promise.all(batch.map((id) => dbDelete(table, id, token)));
    const elapsed = Date.now() - started;
    if (elapsed < DELETE_BATCH_MIN_MS && i + DELETE_BATCH_SIZE < ids.length) {
      await new Promise((r) => setTimeout(r, DELETE_BATCH_MIN_MS - elapsed));
    }
  }
}

export async function bulkInsertChunked<T extends Record<string, unknown>>(
  table: string,
  rows: T[],
  token: string,
) {
  const inserted: unknown[] = [];
  const errors: { index: number; error: string }[] = [];
  let i = 0;
  while (i < rows.length) {
    let bytes = 0;
    let j = i;
    while (j < rows.length && j - i < MAX_CHUNK_ROWS) {
      const rowBytes = JSON.stringify(rows[j]).length;
      if (j > i && bytes + rowBytes > MAX_CHUNK_BYTES) break;
      bytes += rowBytes;
      j++;
    }
    const chunk = rows.slice(i, j);
    const result = await dbBulkInsert<T>(table, chunk, token);
    inserted.push(...result.inserted);
    errors.push(...result.errors.map((e) => ({ index: e.index + i, error: e.error })));
    i = j;
  }
  return { inserted, errors };
}

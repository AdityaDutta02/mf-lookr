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
import { dbBulkInsert } from "@/lib/db";

const MAX_CHUNK_BYTES = 2_000_000; // conservative margin under the gateway's body-size cap
const MAX_CHUNK_ROWS = 900; // stay under dbBulkInsert's hard 1000-row/call cap

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

// lib/db.ts — Terminal AI Database SDK (server-side only)
// Calls /db/* on the Terminal AI gateway using the embed token.
// IMPORTANT: The database is scoped per-APP, not per-user. All users of this app
// share the same tables. The embed token identifies the app for schema routing.

const GATEWAY_URL = process.env.TERMINAL_AI_GATEWAY_URL!

async function fetchWithRetry(url: string, options: RequestInit, maxRetries = 3): Promise<Response> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const res = await fetch(url, options)
    if (res.status !== 429) return res
    const retryAfter = parseInt(res.headers.get('Retry-After') ?? '0', 10)
    const delayMs = retryAfter > 0 ? retryAfter * 1000 : Math.pow(2, attempt + 1) * 1000
    await new Promise<void>((r) => setTimeout(r, delayMs))
  }
  return fetch(url, options)
}

async function dbRequest(method: string, path: string, body?: unknown, embedToken: string = ''): Promise<Response> {
  const res = await fetchWithRetry(`${GATEWAY_URL}/db/${path}`, {
    method,
    headers: { Authorization: `Bearer ${embedToken}`, 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    // Surface the real status + raw body on a non-JSON error response (e.g. a
    // gateway 502/503 HTML page) instead of collapsing every such failure
    // into an undiagnosable "Unknown error" — that string alone gave no way
    // to tell a rate limit, a timeout, and a genuine data error apart.
    const text = await res.text().catch(() => '')
    let message = `DB error ${res.status}`
    try {
      const parsed = JSON.parse(text) as { error?: string }
      if (parsed.error) message = parsed.error
    } catch {
      if (text) message = `DB error ${res.status}: ${text.slice(0, 300)}`
    }
    throw new Error(message)
  }
  return res
}

export async function dbList<T = Record<string, unknown>>(table: string, filters: Record<string, string> = {}, embedToken: string): Promise<T[]> {
  const params = new URLSearchParams(filters)
  const res = await dbRequest('GET', `${table}?${params}`, undefined, embedToken)
  return res.json() as Promise<T[]>
}

export async function dbGet<T = Record<string, unknown>>(table: string, id: string, embedToken: string): Promise<T> {
  const res = await dbRequest('GET', `${table}/${id}`, undefined, embedToken)
  return res.json() as Promise<T>
}

export async function dbInsert<T = Record<string, unknown>>(table: string, row: Record<string, unknown>, embedToken: string): Promise<T> {
  const res = await dbRequest('POST', table, row, embedToken)
  return res.json() as Promise<T>
}

export async function dbUpdate<T = Record<string, unknown>>(table: string, id: string, patch: Record<string, unknown>, embedToken: string): Promise<T> {
  const res = await dbRequest('PATCH', `${table}/${id}`, patch, embedToken)
  return res.json() as Promise<T>
}

export async function dbDelete(table: string, id: string, embedToken: string): Promise<void> {
  await dbRequest('DELETE', `${table}/${id}`, undefined, embedToken)
}

export interface BulkInsertResult<T> {
  inserted: T[]
  errors: { index: number; error: string }[]
}

// POST /db/<table>/bulk — 1 call inserts up to 1000 rows, counts as 1 call against the
// 600/min limit regardless of row count. Always 200; partial success reported per-row in
// `errors` — `unique_violation` there means "already written," safe to treat as done.
const BULK_MAX_ROWS = 1000

export async function dbBulkInsert<T = Record<string, unknown>>(
  table: string,
  rows: Record<string, unknown>[],
  embedToken: string,
): Promise<BulkInsertResult<T>> {
  if (rows.length > BULK_MAX_ROWS) throw new Error(`dbBulkInsert: ${rows.length} rows exceeds the ${BULK_MAX_ROWS}-row cap per call`)
  if (rows.length === 0) return { inserted: [], errors: [] }
  const res = await fetchWithRetry(`${GATEWAY_URL}/db/${table}/bulk`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${embedToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error((err as { error: string }).error ?? `Bulk insert error ${res.status}`)
  }
  return res.json() as Promise<BulkInsertResult<T>>
}

// Terminal AI Gateway SDK — server-side only
// The embed token is received from the viewer shell via postMessage.
// It identifies the APP (not the user) — all users share the same DB and storage.
import config from './validate-config'

const GATEWAY_URL = process.env.TERMINAL_AI_GATEWAY_URL!

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 3,
): Promise<Response> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const res = await fetch(url, options)
    if (res.status !== 429) return res
    const retryAfter = parseInt(res.headers.get('Retry-After') ?? '0', 10)
    const delayMs = retryAfter > 0 ? retryAfter * 1000 : Math.pow(2, attempt + 1) * 1000
    await new Promise<void>((r) => setTimeout(r, delayMs))
  }
  throw new Error('Gateway is busy. Please try again in a moment.')
}

interface GenerateResponse {
  id: string
  content: string
  model_used: string
  usage: { input_tokens: number; output_tokens: number }
  credits_charged: number
}

export async function callGateway(
  messages: { role: string; content: string }[],
  embedToken: string,
  options?: { category?: string; tier?: string; model?: string; system?: string },
): Promise<GenerateResponse> {
  if (!embedToken) throw new Error('Missing embed token')
  const routing = options?.model
    ? { model: options.model }
    : { category: options?.category ?? config.category, tier: options?.tier ?? config.tier }
  const res = await fetchWithRetry(`${GATEWAY_URL}/v1/generate`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${embedToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...routing,
      messages,
      ...(options?.system ? { system: options.system } : {}),
    }),
  })
  if (res.status === 401) {
    throw Object.assign(
      new Error('Session expired. The viewer will deliver a fresh token automatically — retry your request in a moment.'),
      { code: 'TOKEN_EXPIRED', retryable: true },
    )
  }
  if (res.status === 402) {
    const body = await res.json().catch(() => ({})) as { redirect?: string }
    throw Object.assign(
      new Error('Insufficient credits. Please top up to continue.'),
      { code: 'INSUFFICIENT_CREDITS', redirect: body.redirect ?? '/pricing', retryable: false },
    )
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText })) as Record<string, string>
    throw new Error(`Gateway error (${res.status}): ${err.error ?? res.statusText}`)
  }
  return res.json() as Promise<GenerateResponse>
}

// True when this request is part of a sandboxed Agent Preview run. In sandbox mode the gateway
// suppresses real side effects. Decodes claims without verifying signature — never use for a
// security decision, only safe test-time conveniences.
export function isSandbox(embedToken: string | null | undefined): boolean {
  if (!embedToken) return false
  try {
    const part = embedToken.split('.')[1]
    if (!part) return false
    const json = Buffer.from(part.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8')
    const claims = JSON.parse(json) as { type?: string }
    return claims.type === 'sandbox'
  } catch {
    return false
  }
}

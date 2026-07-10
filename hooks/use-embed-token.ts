'use client'
import { useState, useEffect, useRef } from 'react'

const PLATFORM_URL = process.env.NEXT_PUBLIC_TERMINAL_AI_PLATFORM_URL ?? 'https://terminalai.studioionique.com'
const SILENT_REFRESH_MS = 12 * 60 * 1000 // token expires at 15m; refresh at 12m
const OAUTH_STATE_KEY = 'tai_oauth_state'

function genState(): string {
  const buf = new Uint8Array(16)
  crypto.getRandomValues(buf)
  return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('')
}

function readTokenFromFragment(): string | null {
  if (typeof window === 'undefined') return null
  const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : ''
  if (!hash) return null
  const params = new URLSearchParams(hash)
  const token = params.get('token')
  const returnedState = params.get('state')
  const expectedState = sessionStorage.getItem(OAUTH_STATE_KEY)
  sessionStorage.removeItem(OAUTH_STATE_KEY)
  // Reject a fragment token whose state doesn't match what THIS tab generated before redirecting —
  // without this check, an attacker could plant their own token in the fragment (e.g. a crafted
  // link) and have the app silently adopt an attacker-controlled session (session fixation).
  if (!token || !returnedState || !expectedState || returnedState !== expectedState) return null
  // Strip the fragment immediately — a token must never linger in the visible URL / history.
  history.replaceState(null, '', window.location.pathname + window.location.search)
  return token
}

function redirectToAuthorize(appId: string, mode: 'redirect' | 'silent'): string {
  const state = genState()
  sessionStorage.setItem(OAUTH_STATE_KEY, state)
  const url = new URL('/embed/authorize', PLATFORM_URL)
  url.searchParams.set('app_id', appId)
  url.searchParams.set('redirect_uri', window.location.origin + '/')
  url.searchParams.set('state', state)
  url.searchParams.set('mode', mode)
  return url.toString()
}

/**
 * Listens for the embed token delivered by the Terminal AI viewer shell (embedded mode, via
 * window.postMessage) OR bootstraps it via the hosted-login-redirect flow (standalone mode, when
 * this app has no parent window — i.e. it's running at its own subdomain, not inside the
 * marketplace viewer iframe). The token is used to authenticate API calls to the Terminal AI gateway.
 *
 * Usage:
 *   const embedToken = useEmbedToken()
 *   // Pass embedToken to your API routes; they forward it to the gateway
 */
export function useEmbedToken(): string | null {
  const [token, setToken] = useState<string | null>(null)
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // 1. A token in the URL fragment means we just came back from /embed/authorize (standalone) —
    //    adopt it immediately, regardless of embedded/standalone.
    const fragmentToken = readTokenFromFragment()
    if (fragmentToken) {
      setToken(fragmentToken)
      return
    }

    const isStandalone = window.parent === window
    const appId = process.env.NEXT_PUBLIC_TERMINAL_AI_APP_ID

    if (isStandalone) {
      if (!appId) return // scaffolded app must set NEXT_PUBLIC_TERMINAL_AI_APP_ID for standalone mode
      window.location.href = redirectToAuthorize(appId, 'redirect')
      return
    }

    // 2. Embedded mode (has a parent window) — existing postMessage path, unchanged.
    function handleMessage(event: MessageEvent) {
      if (event.data?.type === 'TERMINAL_AI_TOKEN' && typeof event.data.token === 'string') {
        setToken(event.data.token)
      }
    }
    window.addEventListener('message', handleMessage)
    window.parent.postMessage({ type: 'TERMINAL_AI_READY' }, '*')
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  // 3. Standalone silent refresh — once we hold a token, mount a hidden iframe against
  //    /embed/authorize?mode=silent shortly before expiry and adopt whatever it posts back.
  useEffect(() => {
    if (!token || window.parent !== window) return
    const appId = process.env.NEXT_PUBLIC_TERMINAL_AI_APP_ID
    if (!appId) return

    function handleSilentMessage(event: MessageEvent) {
      // Only accept the token from the platform origin — otherwise any other same-page frame
      // could spoof a TERMINAL_AI_TOKEN message and hijack the session.
      if (event.origin !== PLATFORM_URL) return
      if (event.data?.type === 'TERMINAL_AI_TOKEN' && typeof event.data.token === 'string') {
        setToken(event.data.token)
      }
    }
    window.addEventListener('message', handleSilentMessage)

    refreshTimerRef.current = setTimeout(() => {
      const iframe = document.createElement('iframe')
      iframe.style.display = 'none'
      iframe.src = redirectToAuthorize(appId, 'silent')
      document.body.appendChild(iframe)
      setTimeout(() => iframe.remove(), 10_000) // fallback GC if the message never arrives
    }, SILENT_REFRESH_MS)

    return () => {
      window.removeEventListener('message', handleSilentMessage)
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    }
  }, [token])

  return token
}

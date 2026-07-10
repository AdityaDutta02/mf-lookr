const PLATFORM_URL = process.env.NEXT_PUBLIC_TERMINAL_AI_PLATFORM_URL ?? 'https://terminalai.studioionique.com'

/** Send the viewer to the platform's pricing page, with a return trip back to this app. */
export function redirectToPricing(appId: string): void {
  const url = new URL('/pricing', PLATFORM_URL)
  url.searchParams.set('app_id', appId)
  url.searchParams.set('return', window.location.origin + '/')
  window.location.href = url.toString()
}

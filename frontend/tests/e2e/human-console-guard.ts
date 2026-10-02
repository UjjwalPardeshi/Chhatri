/** Shared by the human-console specs: fail a test on any page error or console.error, and reach the real backend through the console proxy. */
import { expect, test as base, type Page } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'

/** Console noise that is not an app bug: aborted requests when a test goes offline on purpose. */
const IGNORED = [/Failed to load resource/, /net::ERR_/]

export const test = base.extend<{ problems: string[] }>({
  problems: [
    async ({ page }, use) => {
      const seen: string[] = []
      page.on('pageerror', (error) => seen.push(`pageerror: ${error.message}`))
      page.on('console', (message) => {
        if (message.type() === 'error' && !IGNORED.some((rx) => rx.test(message.text()))) seen.push(`console.error: ${message.text()}`)
      })
      await use(seen)
      expect(seen, 'page errors and console.error calls').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }

/** Loads the monsoon replay and parks it at `hhmm`, as an operator does before the talk. */
export async function monsoonAt(page: Page, hhmm: string, path = '/live'): Promise<void> {
  await openConsole(page, path)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, hhmm)
}

export async function api(page: Page, method: 'GET' | 'POST', path: string, body: unknown = {}) {
  const res = await page.request.fetch(path, { method, data: method === 'POST' ? body : undefined })
  return (await res.json()) as { ok: boolean; data?: Record<string, unknown>; error?: { code: string } }
}

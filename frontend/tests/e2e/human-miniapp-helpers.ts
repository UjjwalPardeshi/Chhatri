/** Shared steps for the human-miniapp-* specs: a console-error guard and the flag list of the console under test. */
import { expect, type Page } from '@playwright/test'

import { loadScenario, MOCK_HOOK, openConsole, seek } from './helpers'

export const FEATURES = (process.env.E2E_FEATURES ?? '').split(/[\s,]+/).filter((name) => name !== '')
export const has = (name: string): boolean => FEATURES.includes(name)
export const ID = 'S-0142'
export const APP = `/merchant/${ID}/app`

/** Fails the test on any uncaught page error or console.error (the basemap warning is a console.warn and is allowed). */
export function guardErrors(page: Page): string[] {
  const seen: string[] = []
  page.on('pageerror', (error) => seen.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') seen.push(`console.error: ${message.text()}`)
  })
  return seen
}

/** No raw copy key, no undefined/NaN, no sideways scroll on the app screen. */
export async function expectCleanScreen(page: Page): Promise<void> {
  const text = await page.getByTestId('app-root').innerText()
  expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\[object|\{\{|\b(?:nav|home|buy|ask|grv|consent|tracker|why|receipt|slip|settings|help|explain|activity|voice)\.[a-z][\w.]+/)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
}

/** A client-side move to a route, so the mock backend keeps the loaded scenario (a reload restarts it). */
export async function goWithin(page: Page, href: string): Promise<void> {
  await page.evaluate((to) => {
    window.history.pushState({}, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, href)
}

/** Anil's monsoon day at 17:05: paid, instalment answered. Leaves the page on the console. */
export async function anilAt1705(page: Page): Promise<void> {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')
}

/** Takes the mock backend down for `ms` (every API call fails like a lost connection). */
export async function outage(page: Page, ms: number): Promise<void> {
  await page.evaluate(([hook, duration]) => (window as unknown as Record<string, { outage(ms: number): void }>)[String(hook)]?.outage(Number(duration)), [MOCK_HOOK, ms])
}

/** A browser speech recogniser that "hears" `transcript` when the mic is tapped and ends when stopped. */
export async function fakeSpeech(page: Page, transcript: string): Promise<void> {
  await page.addInitScript((heard) => {
    class FakeRecognition extends EventTarget {
      lang = ''
      continuous = false
      interimResults = false
      start(): void {
        setTimeout(() => {
          const event = Object.assign(new Event('result'), { results: [[{ transcript: heard }]] })
          this.dispatchEvent(event)
        }, 50)
      }
      stop(): void {
        setTimeout(() => this.dispatchEvent(new Event('end')), 20)
      }
      abort(): void {
        this.dispatchEvent(new Event('end'))
      }
    }
    Object.assign(window, { SpeechRecognition: FakeRecognition, webkitSpeechRecognition: FakeRecognition })
  }, transcript)
}

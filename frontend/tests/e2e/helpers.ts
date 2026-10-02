/** Shared steps for the console E2E suites (SPEC §22; run in the mock and live projects, B7). */
import { expect, type Locator, type Page } from '@playwright/test'

export const IS_MOCK = !process.env.CONSOLE_URL
/** Test hooks of the mock backend (set in src/main.tsx). */
export const MOCK_HOOK = '__chhatriMock'
export const FONT_HOSTS = /fonts\.googleapis\.com|fonts\.gstatic\.com/
/** Where the screenshot suite writes (kept out of Playwright's own outputDir, see playwright.config.ts). */
export const SCREENS_DIR = 'test-results/screens'
/** A hex drawn at the bottom of the deck scale (sales at or below 40 % of expected, lib/colour.ts SCALE_RED). */
export const RED_HEX = '.leaflet-hexes-pane path[fill="#b91c1c"]'
/** A long replay action (load, seek back) can take a few seconds on a busy machine. */
export const REPLAY_TIMEOUT_MS = 30_000

/** SPEC §17.2 golden strings of the monsoon replay (deck slide 6). */
export const GOLDEN = Object.freeze({
  rows: {
    Alert: 'Red alert from 14:00',
    Sales: '37% of expected for 3 hours',
    Cover: '46 of 46 prepaid',
    Paid: '17:04, with the settlement',
    Total: '₹58,900 · instalments paused',
  },
  labels: ['Z7 · 37% · 46 shops', 'Z3 · 38% · 141 shops', 'Z12 · 47% · 125 shops'],
  z9Label: 'Z9 · 61% of expected',
  z9: "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay.",
})

/** The flags of the console under test (playwright.config.ts passes E2E_FEATURES to the mock as VITE_FEATURES). */
export const E2E_FEATURES: readonly string[] = (process.env.E2E_FEATURES ?? '').split(/[\s,]+/).filter((name) => name !== '')
const LENDER_DECIDES = E2E_FEATURES.includes('x4_lender_request')
/** E2E_FEATURES unset means the flags are whatever the server (live project) or the build says, so either 17:05 line is right. */
const FLAGS_KNOWN = process.env.E2E_FEATURES !== undefined
const PAUSED_BUILT = "Tomorrow's ₹600 instalment is paused."
const PAUSED_LENDER = "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."
const PAUSED_EITHER = /Tomorrow's ₹600 instalment is paused\.|Your lender has paused tomorrow's ₹600 instalment\. It moves to the end of your loan with no penalty\./

/** SPEC §13.4 English lines the demo shows on Anil's and Ramesh's phones. */
export const LINES = Object.freeze({
  intro: 'Anil ji, heavy rain cut your area\'s sales by 63% today.',
  /** The 17:05 line: the lender's grant once the lender decides (E2E_FEATURES has x4_lender_request), else the BUILT pause; either one when E2E_FEATURES is unset. */
  paused: !FLAGS_KNOWN ? PAUSED_EITHER : LENDER_DECIDES ? PAUSED_LENDER : PAUSED_BUILT,
  explain: 'Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales.',
  disputeAck: "Okay, I'm sending this to our team. You'll hear back within 24 hours.",
  slipToHuman: "Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours.",
  personalPaid: "Anil ji, your claim is approved. ₹1,500 credited with today's settlement.",
  officerApproved: 'Anil ji, our team approved your claim. ₹1,500 credited.',
  coverBlocked: /^New cover starts after the waiting period — from 25 August\. It won't apply to tomorrow's alert\.$/,
  soundbox: 'Paytm par ₹1,380 prapt hue — Chhatri se',
})

/** Opens the console once; every later step navigates in-app (a reload restarts the mock). */
export async function openConsole(page: Page, path = '/live'): Promise<void> {
  await page.goto(path)
  await expect(page.locator('.clock-label')).toContainText('Mumbai')
}

export async function loadScenario(page: Page, value: string, clockText: string): Promise<void> {
  await page.getByRole('combobox', { name: 'Scenario' }).selectOption(value)
  await expect(page.locator('.clock-label')).toContainText(clockText, { timeout: REPLAY_TIMEOUT_MS })
  await expect(page.getByRole('combobox', { name: 'Scenario' })).toBeEnabled({ timeout: REPLAY_TIMEOUT_MS })
}

export async function seek(page: Page, hhmm: string): Promise<void> {
  const input = page.getByRole('textbox', { name: 'Seek to time (HH:MM)' })
  /** Phones fold the seek box into the "More replay controls" popover. */
  if (!(await input.isVisible())) await page.getByRole('button', { name: 'More replay controls' }).click()
  await input.fill(hhmm)
  await page.getByRole('button', { name: 'Seek', exact: true }).click()
  await expect(page.locator('.clock-label')).toContainText(hhmm, { timeout: REPLAY_TIMEOUT_MS })
  /** The seek box may have folded away again (phones); the play button is always there and is disabled while busy. */
  await expect(page.getByRole('button', { name: /^(Play|Pause)$/ })).toBeEnabled({ timeout: REPLAY_TIMEOUT_MS })
}

export async function goTo(page: Page, link: string): Promise<void> {
  await page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: link, exact: false }).click()
}

/**
 * The page has drawn: fonts loaded and no loading spinner left. (The live stream keeps a request
 * open for good, so Playwright's "networkidle" never comes against the real backend.)
 */
export async function settled(page: Page): Promise<void> {
  await expect(page.locator('.spinner')).toHaveCount(0, { timeout: REPLAY_TIMEOUT_MS })
  await page.evaluate(async () => {
    await document.fonts.ready
    /** Entrance animations (bubbles, popovers, toasts) finish; endless ones (pulses) are skipped. */
    const finite = document.getAnimations().filter((a) => a.playState === 'running' && a.effect?.getComputedTiming().iterations !== Infinity)
    await Promise.allSettled(finite.map((a) => a.finished))
  })
}

/** The chat bubble whose English line is exactly `text`. */
export function bubble(phone: Locator, text: string | RegExp): Locator {
  return phone.locator('.bubble__en, .bubble__only').filter({ hasText: text })
}

/**
 * Records what the console speaks (SPEC §20 "Sound": Soundbox and voice notes use speechSynthesis
 * when Sarvam is simulated). Headless Chromium has no voices, so the spoken text is captured on
 * `window.__spoken` instead of being played.
 */
export async function recordSpeech(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const said: string[] = []
    Object.assign(window, { __spoken: said })
    window.speechSynthesis.speak = (utterance: SpeechSynthesisUtterance) => {
      said.push(utterance.text)
    }
  })
}

export async function spoken(page: Page): Promise<string[]> {
  return page.evaluate(() => [...((Reflect.get(window, '__spoken') as string[] | undefined) ?? [])])
}

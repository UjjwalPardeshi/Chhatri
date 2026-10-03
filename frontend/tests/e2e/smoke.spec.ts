/**
 * Console smoke suite (SPEC §20, §22; binding decisions B3, B5, B7). Runs against the in-browser
 * mock (project "mock") or a live backend + console (project "live", CONSOLE_URL).
 */
import { expect, test, type Locator, type Page } from '@playwright/test'

import { E2E_FEATURES, FONT_HOSTS, goTo, IS_MOCK, loadScenario, MOCK_HOOK, openConsole, REPLAY_TIMEOUT_MS, seek, settled, SLIP_PRECHECK_SKIP } from './helpers'

test('monsoon golden numbers, local fonts and the tile fallback', async ({ page }) => {
  const fontRequests: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'font' || FONT_HOSTS.test(request.url())) fontRequests.push(request.url())
  })
  await page.route(/tile\.openstreetmap\.org|basemaps\.cartocdn\.com/, (route) => route.abort())
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')

  const map = page.getByTestId('live-map')
  await expect(map).toHaveAttribute('data-tiles', 'fallback')
  await expect(map.getByText('Basemap offline · wards shown')).toBeVisible()
  await expect(map.locator('.pin__card')).toContainText('₹1,380 paid · 17:04')
  await expect(map.locator('.zone-label', { hasText: 'Z7 · 37% · 46 shops' })).toBeVisible()
  await expect(map.locator('.rain-label')).toHaveText('Heavy rain band · since 14:00')

  const card = page.getByRole('region', { name: 'Zone Z7' })
  await expect(card.getByRole('heading')).toHaveText('Zone 7 · 46 shops')
  await expect(card.locator('[data-row="Alert"] dd')).toHaveText('Red alert from 14:00')
  await expect(card.locator('[data-row="Sales"] dd')).toHaveText('37% of expected for 3 hours')
  await expect(card.locator('[data-row="Paid"] dd')).toHaveText('17:04, with the settlement')

  await expect(page.locator('[data-kpi="zones"] .kpi__value')).toHaveText('3')
  await expect(page.locator('[data-kpi="shops"] .kpi__value')).toHaveText('312')
  await expect(page.locator('[data-kpi="ttm"] .kpi__value')).toHaveText('4 min')
  await expect(page.getByText(/Why Zone 9 got nothing/)).toBeVisible()

  expect(await page.evaluate(() => document.fonts.check('16px Ubuntu') && document.fonts.check('16px "Noto Sans Devanagari"', 'मु'))).toBe(true)
  const origin = new URL(page.url()).origin
  expect(fontRequests.filter((url) => !url.startsWith(origin))).toEqual([])
})

test('overview tells the story and jumps into a live test', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: /Chhatri/ })).toBeVisible()
  await expect(page.getByText('Merchant insurance where the claim starts itself')).toBeVisible()
  await expect(page.locator('.control-bar')).toHaveCount(0)
  const storm = page.getByRole('region', { name: 'The storm replay' })
  await storm.scrollIntoViewIfNeeded()
  await expect(storm.getByText('₹58,900 · instalments paused')).toBeVisible()
  const humans = page.getByRole('region', { name: 'Humans in control' })
  await humans.scrollIntoViewIfNeeded()
  await humans.getByRole('button', { name: /Run it/ }).nth(2).click()
  await expect(page).toHaveURL(/\/merchant\/S-0907$/)
  await expect(page.locator('.clock-label')).toContainText('buy cover replay · 18:10')
})

test('phone: "why" answer, dispute case and the officer queue', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await expect(phone.getByText('Paytm · Chhatri')).toBeVisible()
  await expect(phone.getByText('No claim needed')).toBeVisible()
  await phone.getByRole('button', { name: /मुझे इतने ही पैसे क्यों मिले/ }).click()
  await expect(phone.getByText(/^Your usual Tuesday/)).toBeVisible()
  await phone.getByRole('button', { name: /मेरा नुकसान ज़्यादा हुआ/ }).click()
  const chip = phone.getByRole('link', { name: /C-2291/ })
  await expect(chip).toBeVisible()
  await chip.click()
  await expect(page.getByRole('article', { name: 'Case C-2291' })).toBeVisible()
})

test('illness with a mismatched name goes to a human, who approves it', async ({ page }) => {
  test.skip(E2E_FEATURES.includes('n3_slip_precheck'), SLIP_PRECHECK_SKIP)
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:20')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: 'Slip with a different name' }).click()
  await expect(phone.getByRole('link', { name: /C-\d+/ })).toBeVisible()
  await goTo(page, 'Claims')
  const detail = page.getByRole('article', { name: /^Case C-/ })
  await expect(detail.getByText('REFERRED', { exact: true })).toBeVisible()
  await detail.getByRole('button', { name: 'Approve' }).click()
  await expect(detail.getByText('Officer decision')).toBeVisible()
  await expect(detail.locator('.resolution')).toContainText('APPROVED')
})

test('buy cover during a red alert is blocked with a Paytm link', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'buy_cover', 'buy cover replay')
  await goTo(page, 'Merchant phone')
  await expect(page).toHaveURL(/\/merchant\/S-0907$/)
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: 'Red alert tomorrow. Cover me today.' }).click()
  await expect(phone.getByText(/^New cover starts after the waiting period/)).toBeVisible()
  await expect(phone.getByRole('link', { name: /paytm\.me\/sim-/ }).first()).toBeVisible()
})

test('audit chain verifies and integrations show their mode', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '09:00')
  await goTo(page, 'Audit')
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/^Chain valid · \d+ entries/)).toBeVisible()
  await page.getByRole('button', { name: /live · \d+ simulated/ }).click()
  await expect(page.locator('[data-name="weather"]')).toHaveAttribute('data-mode', /LIVE|SIMULATED/)
  await goTo(page, 'Backtest')
  await expect(page.getByText('simulated sales · real Open-Meteo rainfall').first()).toBeVisible()
  await goTo(page, 'Policy')
  await expect(page.getByText('Three live tests in our demo')).toBeVisible()
})

test('stream outage shows the reconnecting pill and recovers', async ({ page }) => {
  test.skip(!IS_MOCK, 'the outage hook exists only in mock mode')
  await openConsole(page)
  await expect(page.locator('.connection-pill')).toHaveCount(0)
  await page.evaluate((hook) => (Reflect.get(window, hook) as { outage: (ms: number) => void }).outage(3_000), MOCK_HOOK)
  await expect(page.getByText('Reconnecting…')).toBeVisible()
  await expect(page.locator('.connection-pill')).toHaveCount(0, { timeout: 20_000 })
})

test.describe('phone-sized screen', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('no page scrolls sideways at 390 px', async ({ page }) => {
    await openConsole(page)
    const widths: Record<string, number> = {}
    for (const link of ['Overview', 'Live map', 'Claims', 'Merchant phone', 'Audit', 'Backtest', 'Policy']) {
      await goTo(page, link)
      await settled(page)
      widths[link] = await page.evaluate(() => document.documentElement.scrollWidth)
    }
    expect(Object.values(widths).every((w) => w <= 390), JSON.stringify(widths)).toBe(true)
  })
})

/** The five console pages the projector shows (fs-08 13.3), at the 1280×720 the e2e suite runs in. */
/** The Evals page exists only with h25_evals (E2E_FEATURES); it is measured whenever its nav link is there. */
const PROJECTOR_PAGES = ['Live map', 'Claims', 'Audit', 'Backtest', 'Policy', ...(E2E_FEATURES.includes('h25_evals') ? ['Evals'] : [])]

/** Widest content of the page and of its scroll container, against their visible widths: nothing may scroll sideways. */
async function sidewaysOverflow(page: Page): Promise<{ page: number; main: number }> {
  return page.evaluate(() => {
    const doc = document.documentElement
    const main = document.querySelector('.app-main')
    return { page: doc.scrollWidth - doc.clientWidth, main: main ? main.scrollWidth - main.clientWidth : 0 }
  })
}

test('the Evals page says NOT MEASURED until a run is stored (h25_evals)', async ({ page }) => {
  test.skip(!E2E_FEATURES.includes('h25_evals'), 'the page is behind h25_evals: run with E2E_FEATURES=h25_evals')
  await openConsole(page)
  await goTo(page, 'Evals')
  await expect(page.getByRole('heading', { name: 'AI evaluation' })).toBeVisible()
  await expect(page.getByTestId('eval-none')).toContainText('NOT MEASURED')
})

test.describe('projector 1280×720', () => {
  test('no console page scrolls sideways', async ({ page }) => {
    await openConsole(page)
    await loadScenario(page, 'monsoon', 'monsoon replay')
    await seek(page, '17:05')
    const overflow: Record<string, { page: number; main: number }> = {}
    for (const link of PROJECTOR_PAGES) {
      await goTo(page, link)
      await settled(page)
      overflow[link] = await sidewaysOverflow(page)
    }
    const wide = Object.entries(overflow).filter(([, o]) => o.page > 0 || o.main > 0)
    expect(wide, JSON.stringify(overflow)).toEqual([])
  })

  test('presenter mode (console_polish): no sideways scroll, and no text under 12 px on Live and Claims', async ({ page }) => {
    await openConsole(page, '/live?presenter=1')
    test.skip((await page.getByRole('button', { name: 'Present' }).count()) === 0, 'presenter mode is behind the console_polish flag (VITE_FEATURES=console_polish)')
    await expect(page.locator('.app')).toHaveAttribute('data-presenter', 'on')
    await loadScenario(page, 'monsoon', 'monsoon replay')
    await seek(page, '17:05')
    const overflow: Record<string, { page: number; main: number }> = {}
    const smallest: Record<string, { size: number; where: string }> = {}
    for (const link of PROJECTOR_PAGES) {
      await goTo(page, link)
      await settled(page)
      overflow[link] = await sidewaysOverflow(page)
      if (link === 'Live map' || link === 'Claims') smallest[link] = await smallestText(page)
    }
    expect(Object.entries(overflow).filter(([, o]) => o.page > 0 || o.main > 0), JSON.stringify(overflow)).toEqual([])
    for (const [link, text] of Object.entries(smallest)) expect(text.size, `${link}: ${text.where}`).toBeGreaterThanOrEqual(12)
  })

  /**
   * The right panel scrolls (the activity feed sits below the fold), but its first four cards are the story: the moment,
   * the zone, the numbers and the slow-day note must all be on screen at once, with no scrolling, at 17:04.
   */
  for (const [mode, entry] of [
    ['normal', '/live?presenter=0'],
    ['presenter', '/live?presenter=1'],
  ] as const) {
    test(`the right panel shows the moment card and the whole slow-day note at 17:04 in ${mode} type (console_polish)`, async ({ page }) => {
      await openConsole(page, entry)
      test.skip((await page.getByRole('button', { name: 'Present' }).count()) === 0, 'the moment card is behind the console_polish flag (VITE_FEATURES=console_polish)')
      await loadScenario(page, 'monsoon', 'monsoon replay')
      await seek(page, '17:04')
      await expect(page.getByRole('region', { name: 'Trigger to payout' })).toBeVisible()
      const cut = await page.evaluate(() => {
        const panel = document.querySelector('.home__panel')
        const note = document.querySelector('.home__panel .explanations')
        return panel && note ? Math.ceil(note.getBoundingClientRect().bottom - panel.getBoundingClientRect().bottom) : Number.NaN
      })
      expect(cut, `the panel cuts ${cut} px off the slow-day note`).toBeLessThanOrEqual(0)
    })
  }
})

test('presenter mode (console_polish): after the Present click, Space plays and 2 jumps to 16:59 (AC-PM-03)', async ({ page }) => {
  await openConsole(page)
  const present = page.getByRole('button', { name: 'Present' })
  test.skip((await present.count()) === 0, 'presenter mode is behind the console_polish flag (VITE_FEATURES=console_polish)')
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await present.click()
  await expect(present).toHaveAttribute('aria-pressed', 'true')
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible()
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
  await page.keyboard.press('2')
  await expect(page.locator('.clock-label')).toContainText('16:59', { timeout: REPLAY_TIMEOUT_MS })
  await page.keyboard.press('p')
  await expect(present).toHaveAttribute('aria-pressed', 'false')
})

/** The computed animation duration of an element (Chromium reports the 1 ms of the reduced-motion rule as 0.001s). */
const duration = (locator: Locator) => locator.evaluate((element) => getComputedStyle(element).animationDuration)

test('presenter mode (console_polish): the moment card and the pop-ups stop animating under reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openConsole(page, '/live?presenter=1')
  test.skip((await page.getByRole('button', { name: 'Present' }).count()) === 0, 'presenter mode is behind the console_polish flag (VITE_FEATURES=console_polish)')
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:02')
  const moment = page.getByRole('region', { name: 'Trigger to payout' })
  await expect(moment).toBeVisible()
  expect(await duration(moment)).toBe('0.001s')
  await page.keyboard.press('?')
  await expect(page.getByRole('region', { name: 'Presenter keys' })).toBeVisible()
  expect(await duration(page.getByRole('region', { name: 'Presenter keys' }))).toBe('0.001s')
})

/** The smallest rendered text on the page: every visible text node's computed font size (AC-PM-01). */
async function smallestText(page: Page): Promise<{ size: number; where: string }> {
  return page.evaluate(() => {
    let found = { size: Number.POSITIVE_INFINITY, where: '' }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim()
      const element = node.parentElement
      if (!text || !element) continue
      const style = getComputedStyle(element)
      const box = element.getBoundingClientRect()
      if (style.display === 'none' || style.visibility === 'hidden' || box.width <= 1 || box.height <= 1) continue
      const size = Number.parseFloat(style.fontSize)
      if (size < found.size) found = { size, where: `${element.tagName.toLowerCase()}.${String(element.className)} "${text.slice(0, 40)}"` }
    }
    return found
  })
}

test('switching scenario on another page, then Merchant phone at once, opens the new merchant', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await goTo(page, 'Claims')
  await expect(page).toHaveURL(/\/claims/)
  await page.getByRole('combobox', { name: 'Scenario' }).selectOption('buy_cover')
  await goTo(page, 'Merchant phone')
  await expect(page).toHaveURL(/\/merchant\/S-0907$/)
  await expect(page.locator('.clock-label')).toContainText('buy cover replay')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: 'Red alert tomorrow. Cover me today.' }).click()
  await expect(phone.getByText(/^New cover starts after the waiting period/)).toBeVisible()
})

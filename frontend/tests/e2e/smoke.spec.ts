/**
 * Console smoke suite (SPEC §20, §22; binding decisions B3, B5, B7). Runs against the in-browser
 * mock (project "mock") or a live backend + console (project "live", CONSOLE_URL).
 */
import { expect, test } from '@playwright/test'

import { FONT_HOSTS, goTo, IS_MOCK, loadScenario, MOCK_HOOK, openConsole, seek, settled } from './helpers'

test('monsoon golden numbers, local fonts and the tile fallback', async ({ page }) => {
  const fontRequests: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'font' || FONT_HOSTS.test(request.url())) fontRequests.push(request.url())
  })
  await page.route(/basemaps\.cartocdn\.com/, (route) => route.abort())
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

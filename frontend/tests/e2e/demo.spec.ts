/**
 * The live demo, end to end (SPEC §0, §13.6 three live tests, §17.2 golden numbers, §20; deck
 * slides 6-8; binding decisions B2-B5). Runs against the real backend + console (project "live",
 * CONSOLE_URL) and against the in-browser mock (project "mock"). Every test loads its own scenario,
 * so the order of tests never matters.
 */
import { expect, test, type Page } from '@playwright/test'

import { bubble, E2E_FEATURES, goTo, GOLDEN, LINES, loadScenario, openConsole, recordSpeech, RED_HEX, REPLAY_TIMEOUT_MS, seek, SLIP_PRECHECK_SKIP, spoken } from './helpers'

test.describe.configure({ timeout: 120_000 })

async function openPhone(page: Page, merchant: string) {
  await goTo(page, 'Merchant phone')
  await expect(page).toHaveURL(new RegExp(`/merchant/${merchant}$`))
  const phone = page.getByTestId('phone')
  await expect(phone.getByText('Paytm · Chhatri')).toBeVisible()
  return phone
}

test('monsoon replay: play, seek to 17:10, and the map, card, KPIs, Z9 and feed read like deck slide 6', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay · 08:00')
  const map = page.getByTestId('live-map')
  await expect(map.locator('.leaflet-hexes-pane path').first()).toBeAttached()
  expect(await map.locator(RED_HEX).count()).toBe(0)

  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.locator('.clock-label')).not.toContainText('· 08:00 ·', { timeout: REPLAY_TIMEOUT_MS })
  await seek(page, '17:10')

  for (const label of GOLDEN.labels) await expect(map.locator('.zone-label', { hasText: label })).toBeVisible()
  await expect(map.locator('.zone-label--slow strong')).toHaveText(GOLDEN.z9Label)
  await expect(map.locator('.rain-label')).toHaveText('Heavy rain band · since 14:00')
  await expect(map.locator('.pin__card')).toContainText('₹1,380 paid · 17:04')
  await expect.poll(() => map.locator(RED_HEX).count()).toBeGreaterThan(10)

  const card = page.getByRole('region', { name: 'Zone Z7' })
  await expect(card.getByRole('heading')).toHaveText('Zone 7 · 46 shops')
  await expect(card.locator('.zone-card__pct')).toHaveText('37%')
  for (const [label, value] of Object.entries(GOLDEN.rows)) await expect(card.locator(`[data-row="${label}"] dd`)).toHaveText(value)

  await expect(page.locator('[data-kpi="zones"] .kpi__value')).toHaveText('3')
  await expect(page.locator('[data-kpi="shops"] .kpi__value')).toHaveText('312')
  await expect(page.locator('[data-kpi="ttm"] .kpi__value')).toHaveText('4 min')
  await expect(page.locator('.explanation[data-zone="Z9"]')).toHaveText(GOLDEN.z9)
  await expect(page.locator('.explanation[data-zone="Z9"]')).toBeInViewport({ ratio: 1 })

  const feed = page.getByRole('region', { name: 'Live events' })
  await expect(feed.getByText('Area triggers fired')).toBeVisible()
  await expect(feed.getByText('Area payouts credited')).toBeVisible()
  await expect(feed.getByText('Loan instalments paused')).toBeVisible()
})

test('Anil’s phone after the storm: payout, pause, Soundbox, “why” and “dispute” to case C-2291', async ({ page }) => {
  await recordSpeech(page)
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:02')
  await page.getByRole('button', { name: 'Enable sound' }).click()
  await expect(page.getByRole('button', { name: 'Sound on' })).toHaveAttribute('aria-pressed', 'true')
  const phone = await openPhone(page, 'S-0142')
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(bubble(phone, LINES.paused)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
  await page.getByRole('button', { name: 'Pause', exact: true }).click()

  await expect(bubble(phone, LINES.intro)).toBeAttached()
  await expect(phone.locator('.payout-card__amount')).toHaveText('₹1,380')
  await expect(phone.getByText('No claim needed')).toBeVisible()
  await expect(page.locator('.soundbox-device__hi')).toHaveText(`“${LINES.soundbox}”`)
  await expect.poll(() => spoken(page)).toContain(LINES.soundbox)

  await phone.getByRole('button', { name: /मुझे इतने ही पैसे क्यों मिले/ }).click()
  await expect(bubble(phone, LINES.explain)).toBeVisible()
  await phone.getByRole('button', { name: /मेरा नुकसान ज़्यादा हुआ/ }).click()
  await expect(bubble(phone, LINES.disputeAck)).toBeVisible()
  const chip = phone.getByRole('link', { name: 'Sent to a claims officer · case C-2291' })
  await expect(chip).toBeVisible()
  await chip.click()
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await expect(detail.getByText('Dispute', { exact: true })).toBeVisible()
  await expect(page.locator('.queue__item', { hasText: 'C-2291' })).toBeVisible()
})

test('HUMAN: a slip with another name goes to an officer, who approves it; ₹1,500 reaches the phone', async ({ page }) => {
  test.skip(E2E_FEATURES.includes('n3_slip_precheck'), SLIP_PRECHECK_SKIP)
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:25')
  const phone = await openPhone(page, 'S-0142')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await expect(bubble(phone, 'Get well soon. Please send one photo of the hospital slip.')).toBeVisible()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: 'Slip with a different name' }).click()
  await expect(bubble(phone, LINES.slipToHuman)).toBeVisible()
  const chip = phone.getByRole('link', { name: /case C-2291/ })
  await expect(chip).toBeVisible()

  await goTo(page, 'Claims')
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await expect(detail.getByText('REFERRED', { exact: true })).toBeVisible()
  await expect(detail.getByText('Name on the slip doesn’t match KYC', { exact: true })).toBeVisible()
  await detail.getByRole('button', { name: 'Approve' }).click()
  await expect(detail.getByText('Officer decision')).toBeVisible()
  await expect(detail.locator('.resolution')).toContainText('APPROVED')
  await expect(detail.locator('.resolution')).toContainText(/₹1,500 credited to Anil.s Tea Stall at \d\d:\d\d, with the settlement\./, { timeout: REPLAY_TIMEOUT_MS })
  await expect(detail.getByText(/^Personal claim ₹1,500 for Anil.s Tea Stall sent to a human: the name on the slip/)).toBeVisible()

  await detail.getByRole('link', { name: 'Open the phone' }).click()
  await expect(bubble(phone, LINES.officerApproved)).toBeVisible()
  await expect(phone.locator('.payout-card__amount').last()).toHaveText('₹1,500')
})

test('illness: one photo of the slip pays ₹1,500 the same day', async ({ page }) => {
  test.skip(E2E_FEATURES.includes('n3_slip_precheck'), SLIP_PRECHECK_SKIP)
  await openConsole(page)
  await loadScenario(page, 'illness', 'illness replay')
  await seek(page, '11:25')
  const phone = await openPhone(page, 'S-0142')
  await expect(bubble(phone, 'Your shop has been closed since yesterday. Is everything okay?')).toBeAttached()
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: "Anil's admission slip" }).click()
  await expect(bubble(phone, LINES.personalPaid)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
  await expect(phone.locator('.payout-card__amount').last()).toHaveText('₹1,500')
  await expect(page.locator('.clock-label')).toContainText('11:30')
})

test('BLOCKED: Ramesh asks for cover the evening before a red alert and gets a Paytm link for later', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'buy_cover', 'buy cover replay')
  await seek(page, '18:10')
  const phone = await openPhone(page, 'S-0907')
  await phone.getByRole('button', { name: 'Red alert tomorrow. Cover me today.' }).click()
  await expect(bubble(phone, LINES.coverBlocked)).toBeVisible()
  await expect(phone.getByRole('link', { name: /paytm\.me\/sim-|paytm/ }).first()).toBeVisible()
  await expect(page.getByText('Cover bought after an alert')).toBeVisible()
})

test('audit chain verifies; backtest and policy show the real report and rules', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:10')
  await goTo(page, 'Audit')
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/^Chain valid · \d+ entries/)).toBeVisible()
  await goTo(page, 'Backtest')
  await expect(page.getByText('simulated sales · real Open-Meteo rainfall').first()).toBeVisible()
  await expect(page.getByText('More than a weather-only trigger').first()).toBeVisible()
  await expect(page.getByText('Fewer than a weather-only trigger').first()).toBeVisible()
  await expect(page.getByText('All of them').first()).toBeVisible()
  await goTo(page, 'Policy')
  await expect(page.getByText('Three live tests in our demo')).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Area drop during an alert, index clear' })).toBeVisible()
})

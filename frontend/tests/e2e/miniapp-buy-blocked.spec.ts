/**
 * S3 Buy while an alert is on (fs-04 AC-13 to AC-17, card 3.9): Ramesh asks for cover on the buy_cover replay, is told
 * the truth (blocked, starts 25 August, the price and first payment), sees a SIMULATED link, simulates the payment and
 * sees the new start date. Run with `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-buy-blocked`.
 * The page is not reloaded after the scenario is loaded (a reload restarts the mock backend), so the standalone route
 * is reached through the browser history. `E2E_SHOTS_DIR` saves a screenshot of each size.
 */
import { expect, test, type Page } from '@playwright/test'

import { loadScenario, openConsole, REPLAY_TIMEOUT_MS } from './helpers'

const FEATURES = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim())
const FLAG_ON = FEATURES.includes('n1_miniapp')
/** With n6_consents on, the two required boxes are ticked first (fs-07 9.5, AC-N6-08). */
const CONSENTS_ON = FEATURES.includes('n6_consents')
const SHOTS_DIR = process.env.E2E_SHOTS_DIR
test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS_DIR) await page.screenshot({ path: `${SHOTS_DIR}/${name}.png` })
}

/** A client-side move to a route, so the mock backend keeps the loaded scenario. */
async function goWithin(page: Page, href: string): Promise<void> {
  await page.evaluate((to) => {
    window.history.pushState({}, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, href)
}

test('phone 390 by 844: blocked, starts 25 August, simulated link, paid', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openConsole(page)
  await loadScenario(page, 'buy_cover', 'buy cover replay')
  await goWithin(page, '/merchant/S-0907/app?lang=en&screen=buy')
  if (CONSENTS_ON) {
    await expect(page.getByTestId('buy-check')).toBeDisabled()
    await page.getByTestId('buy-consent-SALES_DATA_FOR_CLAIM').check()
    await page.getByTestId('buy-consent-SETTLEMENT_DEDUCTION').check()
  }
  await page.getByTestId('buy-check').click()
  const result = page.getByTestId('buy-result')
  await expect(result).toHaveAttribute('data-outcome', 'BLOCKED', { timeout: REPLAY_TIMEOUT_MS })
  await expect(page.getByTestId('buy-starts-on')).toHaveText('25 August')
  await expect(page.getByTestId('buy-price-per-day')).toHaveText('₹14.16')
  await expect(page.getByTestId('buy-first-payment')).toHaveText('₹424.80')
  await expect(page.getByTestId('screen-buy')).not.toContainText(/approved/i)
  await expect(page.getByTestId('buy-link-mode')).toContainText('SIMULATED')
  await shot(page, 'buy-blocked-390')
  await page.getByTestId('buy-simulate-pay').click()
  await expect(page.getByTestId('buy-paid')).toContainText('25 August')
  await expect(page.getByTestId('app-nba')).toHaveAttribute('data-nba', 'home_after_paid')
})

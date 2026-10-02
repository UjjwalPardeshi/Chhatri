/**
 * Claims, the tracker, Why and the receipt for Anil (fs-04 AC-17, AC-26, AC-27, AC-31, card 3.10): the list, the five steps
 * with their times, why this amount with its sources and the counterfactual, and the receipt with its fingerprint and
 * "Check the log". Run with `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-area-claim`. The page is
 * not reloaded after the replay moves (a reload restarts the mock backend), so the app is reached through the history.
 * `E2E_SHOTS_DIR` saves a screenshot of the phone size and of the frame inside the console.
 */
import { expect, test, type Page } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')
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

async function anilAt1705(page: Page): Promise<void> {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')
}

test('phone 390 by 844: Anil opens his claim, asks why, and reads the receipt', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await anilAt1705(page)
  await goWithin(page, '/merchant/S-0142/app?lang=en&screen=claims')
  const card = page.getByTestId('claim-card-CL-000142')
  await expect(card).toContainText('₹1,380')
  await expect(card).toContainText('Paid')
  await card.getByRole('link').click()

  await expect(page.getByTestId('screen-claim')).toHaveAttribute('data-state', 'ready')
  for (const id of ['detected', 'checked', 'decided', 'paid', 'edi']) await expect(page.getByTestId(`claim-step-${id}`)).toHaveAttribute('data-status', 'completed')
  await expect(page.getByTestId('claim-step-detected').locator('time')).toHaveText('17:00')
  await expect(page.getByTestId('claim-step-paid').locator('time')).toHaveText('17:04')
  await expect(page.getByTestId('claim-step-edi').locator('time')).toHaveText('17:05')
  await expect(page.getByTestId('claim-step-decided')).toContainText('₹1,380')
  await expect(page.getByTestId('claim-step-paid')).toContainText('SIMULATED')
  await expect(page.getByTestId('claim-step-edi')).toContainText('SIMULATED')
  await expect(page.getByTestId('screen-claim')).not.toContainText(/chhatri (has )?paused/i)
  await shot(page, 'claim-390')

  await expect(page.getByTestId('app-nba')).toHaveAttribute('data-nba', 'see_why')
  await page.getByTestId('app-nba-action').click()
  await expect(page.getByTestId('why-formula')).toHaveText('½ × ₹4,380 × 63% = ₹1,380')
  const rows = page.getByTestId('why-numbers').getByTestId(/^why-row-/)
  await expect(rows).toHaveCount(6)
  for (const row of await rows.all()) await expect(row.getByTestId('why-badges').getByTestId('source-badge').first()).toBeVisible()
  await expect(page.getByTestId('why-counterfactual')).toBeVisible()
  await expect(page.getByTestId('source-missing')).toHaveCount(0)

  await page.getByTestId('app-nba-action').click()
  await expect(page.getByTestId('receipt-decision-id')).toHaveText('D-000142')
  await expect(page.getByTestId('receipt-rules-version')).toHaveText('pilot-0.1')
  await expect(page.getByTestId('receipt-formula')).toHaveText('½ × ₹4,380 × 63% = ₹1,380')
  await expect(page.getByTestId('receipt-audit-prefix')).toHaveText(/^[0-9a-f]{12}$/)
  await expect(page.getByTestId('receipt-sources').getByTestId('source-badge').first()).toContainText('SIMULATED')
  await expect(page.getByTestId('receipt-grievance-path')).toContainText('We reply within 24 hours.')
  await expect(page.getByTestId('receipt-simulated')).toBeVisible()
  await page.getByTestId('receipt-check-log').click()
  await expect(page.getByTestId('receipt-log-result')).toHaveText(/^Log unbroken, \d+ entries$/)
  await shot(page, 'receipt-390')
})

test('console 1280 by 720: the claim inside the phone frame next to the console', async ({ page }) => {
  await anilAt1705(page)
  await goWithin(page, '/merchant/S-0142?lang=en&screen=claim&claim=CL-000142')
  const frame = page.getByTestId('app-frame')
  await expect(frame.getByTestId('screen-claim')).toHaveAttribute('data-state', 'ready')
  await expect(frame.getByTestId('claim-step-edi')).toHaveAttribute('data-status', 'completed')
  await expect(frame.getByTestId('claim-dispute-button')).toBeVisible()
  await shot(page, 'claim-frame-1280')
})

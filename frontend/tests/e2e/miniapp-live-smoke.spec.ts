/**
 * Home, tracker and receipt for Anil against a running backend (card 3.10, project `live`): one spec. The console under
 * test must have `n1_miniapp` on (it is the console's own build), and the backend must hold the claims and receipt
 * routes. Run with `CONSOLE_URL=http://127.0.0.1:5173 npx playwright test --project=live miniapp-live-smoke`. It is
 * skipped in the mock project, which has its own suites for the same screens.
 */
import { expect, test, type Page } from '@playwright/test'

import { IS_MOCK, loadScenario, openConsole, REPLAY_TIMEOUT_MS, seek } from './helpers'

test.skip(IS_MOCK, 'this suite runs against a live backend: set CONSOLE_URL and use --project=live')

/** A client-side move to a route, so the console keeps the loaded scenario and the stream it already opened. */
async function goWithin(page: Page, href: string): Promise<void> {
  await page.evaluate((to) => {
    window.history.pushState({}, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, href)
}

test('Home, tracker and receipt for Anil', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')

  await goWithin(page, '/merchant/S-0142/app?lang=en')
  await expect(page.getByTestId('screen-home')).toHaveAttribute('data-state', 'ready', { timeout: REPLAY_TIMEOUT_MS })
  await expect(page.getByTestId('home-latest-claim')).toContainText('₹1,380')
  await expect(page.getByTestId('app-nba')).toHaveAttribute('data-nba', 'see_why')

  await page.getByTestId('app-tab-claims').click()
  await expect(page.getByTestId('claims-list')).toBeVisible()
  await page.getByTestId('claim-card-CL-000142').getByRole('link').click()
  for (const id of ['detected', 'checked', 'decided', 'paid', 'edi']) await expect(page.getByTestId(`claim-step-${id}`)).toHaveAttribute('data-status', 'completed')
  await expect(page.getByTestId('claim-step-decided')).toContainText('₹1,380')

  await page.getByTestId('claim-open-receipt').click()
  await expect(page.getByTestId('receipt-decision-id')).toHaveText('D-000142')
  await expect(page.getByTestId('receipt-rules-version')).toHaveText('pilot-0.1')
  await expect(page.getByTestId('receipt-formula')).toHaveText('½ × ₹4,380 × 63% = ₹1,380')
  await expect(page.getByTestId('receipt-sources').getByTestId('source-badge').first()).toBeVisible()
  await expect(page.getByTestId('receipt-audit-prefix')).toHaveText(/^[0-9a-f]{12}$/)
  await expect(page.getByTestId('source-missing')).toHaveCount(0)
  await page.getByTestId('receipt-check-log').click()
  await expect(page.getByTestId('receipt-log-result')).toHaveText(/^Log unbroken, \d+ entries$/)
})

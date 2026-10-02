/**
 * "This is wrong" (fs-04 AC-22, AC-23, card 3.10): Anil taps the button on his ₹1,380 payout, the dispute phrase goes
 * to the chat route, the thanks (DISPUTE_ACK) shows in a toast, a question about the payout opens under the claim and
 * in the list, and the amount stays ₹1,380. When the officer closes the case in the console, the card shows closed
 * with the officer's note and the same amount. Run with `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-dispute`.
 */
import { expect, test, type Page } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')
const SHOTS_DIR = process.env.E2E_SHOTS_DIR
test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

const CLAIM = '/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142'

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

test('dispute: a question opens, the amount stays, the officer closes it', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:12')
  await goWithin(page, CLAIM)
  await page.getByTestId('claim-dispute-button').click()

  await expect(page.getByTestId('app-toast-host')).toContainText("Okay, I'm sending this to our team. You'll hear back within 24 hours.")
  const toast = page.getByTestId('app-toast-host').locator('[data-sonner-toast]')
  await expect.poll(async () => (await toast.boundingBox())?.y ?? -1).toBeGreaterThanOrEqual(56)
  const card = page.getByTestId('claim-dispute-card')
  await expect(card).toContainText('Question open')
  await expect(card.getByTestId('claim-dispute-amount')).toHaveText('₹1,380')
  await expect(page.getByTestId('claim-case-chip')).toHaveText('Sent to a claims officer · case C-2291')
  await expect(page.getByTestId('claim-clock')).toHaveText('24 hours left')
  await expect(page.getByTestId('claim-dispute-button')).toHaveCount(0)
  await expect(page.getByTestId('claim-amount')).toHaveText('₹1,380')
  await shot(page, 'dispute-390')

  await goWithin(page, '/merchant/S-0142/app?lang=en&screen=claims')
  const list = page.getByTestId('claims-list')
  await expect(list.getByRole('listitem')).toHaveCount(2)
  await expect(list.getByTestId('claim-card-C-2291')).toContainText('Question about a payout')
  await expect(list.getByTestId('claim-card-CL-000142')).toContainText('₹1,380')

  await page.setViewportSize({ width: 1280, height: 720 })
  await goWithin(page, '/claims')
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await detail.getByRole('button', { name: 'Confirm payout' }).click()
  await expect(detail.locator('.resolution')).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await goWithin(page, CLAIM)
  const closed = page.getByTestId('claim-dispute-card')
  await expect(closed).toContainText('Question closed. Amount unchanged.')
  await expect(closed.getByTestId('claim-dispute-amount')).toHaveText('₹1,380')
  await expect(page.getByTestId('claim-resolution')).toContainText('Payout confirmed by a claims officer')
  await expect(page.getByTestId('claim-amount')).toHaveText('₹1,380')
})

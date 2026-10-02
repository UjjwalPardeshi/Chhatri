/**
 * A hospital-cash claim that goes to a person (fs-04 AC-19, AC-20, card 3.10): the slip names someone else, so the claim
 * is with a claims officer (case chip, 24 hour clock, Paid and the EDI holiday pending); the officer approves it in the
 * console and, once the credit time has passed, the app says "Approved by a claims officer", Paid is done, and the
 * receipt shows the soft check the officer cleared. Run with
 * `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-referred`.
 */
import { expect, test, type Page } from '@playwright/test'

import { goTo, loadScenario, openConsole, seek } from './helpers'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')
const SHOTS_DIR = process.env.E2E_SHOTS_DIR
test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

const CLAIM = '/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000001'

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

test('illness_mismatch: with a claims officer, then approved by one', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:20')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: 'Slip with a different name' }).click()
  await expect(phone.getByRole('link', { name: /C-\d+/ })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await goWithin(page, CLAIM)
  await expect(page.getByTestId('claim-step-decided')).toHaveAttribute('data-status', 'current')
  await expect(page.getByTestId('claim-step-decided')).toContainText('With a claims officer')
  await expect(page.getByTestId('claim-case-chip')).toHaveText('Sent to a claims officer · case C-2291')
  await expect(page.getByTestId('claim-clock')).toHaveText(/^\d+ hours left$/)
  await expect(page.getByTestId('claim-step-paid')).toHaveAttribute('data-status', 'pending')
  await expect(page.getByTestId('claim-step-edi')).toHaveAttribute('data-status', 'pending')
  await expect(page.getByTestId('claim-dispute-button')).toHaveCount(0)
  await shot(page, 'referred-390')

  await page.setViewportSize({ width: 1280, height: 720 })
  await goWithin(page, '/claims')
  const detail = page.getByRole('article', { name: /^Case C-/ })
  await detail.getByRole('button', { name: 'Approve' }).click()
  await expect(detail.getByText('Officer decision')).toBeVisible()
  await seek(page, '11:30')

  await page.setViewportSize({ width: 390, height: 844 })
  await goWithin(page, CLAIM)
  await expect(page.getByTestId('claim-step-decided')).toContainText('Approved by a claims officer')
  await expect(page.getByTestId('claim-step-decided')).toContainText('₹1,500')
  await expect(page.getByTestId('claim-step-paid')).toHaveAttribute('data-status', 'completed')
  await expect(page.getByTestId('claim-case-chip')).toHaveCount(0)

  await page.getByTestId('claim-open-receipt').click()
  await expect(page.getByTestId('receipt-check-NAME_MATCHES_KYC')).toHaveAttribute('data-status', 'WAIVED_BY_OFFICER')
  await expect(page.getByTestId('receipt-outcome')).toHaveText('Approved by a claims officer')
})

/**
 * The instalment step of the claim tracker and the receipt, with the lender deciding (x4_lender_request on) or the
 * built pause (off), and with the lender unreachable (fallback switch). The words must never say Chhatri paused it
 * when the lender decides. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-lender`.
 */
import { expect, test } from '@playwright/test'

import { loadScenario, MOCK_HOOK, openConsole, seek } from './helpers'
import { goWithin, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp'), 'needs n1_miniapp')
test.use({ viewport: { width: 390, height: 844 } })

const CLAIM = '/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142'

async function monsoon(page: import('@playwright/test').Page, forced: boolean): Promise<void> {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  if (forced) await page.evaluate((hook) => (window as unknown as Record<string, { setLenderForced(on: boolean): void }>)[hook]?.setLenderForced(true), MOCK_HOOK)
  await seek(page, '17:05')
}

test('the lender answers: the step says the lender decided, SIMULATED, never that Chhatri paused it', async ({ page }) => {
  test.skip(!has('x4_lender_request'), 'needs x4_lender_request')
  const errors = guardErrors(page)
  await monsoon(page, false)
  await goWithin(page, CLAIM)
  const edi = page.getByTestId('claim-step-edi')
  await expect(edi).toHaveAttribute('data-status', 'completed')
  await expect(edi).toContainText(/lender/i)
  await expect(edi).toContainText('SIMULATED')
  await expect(edi).not.toContainText(/chhatri (has )?paused/i)
  await page.getByTestId('claim-open-receipt').click()
  await expect(page.getByTestId('receipt-document')).toContainText("Your lender has paused the ₹600 instalment")
  expect(errors).toEqual([])
})

test('the lender cannot be reached: the instalment is due as usual and the app says so', async ({ page }) => {
  test.skip(!has('x4_lender_request'), 'needs x4_lender_request')
  await monsoon(page, true)
  await goWithin(page, CLAIM)
  const edi = page.getByTestId('claim-step-edi')
  await expect(edi).toContainText('We could not reach your lender. Your instalment is due as usual.')
  await expect(edi).not.toContainText(/paused/i)
})

test('without x4_lender_request the instalment step does not claim a lender answered', async ({ page }) => {
  test.skip(has('x4_lender_request'), 'only when x4_lender_request is off')
  await monsoon(page, false)
  await goWithin(page, CLAIM)
  const edi = page.getByTestId('claim-step-edi')
  await expect(edi).toBeVisible()
  await expect(edi).toContainText('SIMULATED')
  await expect(edi).not.toContainText(/lender (has )?(paused|granted|decided)/i)
})

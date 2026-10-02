/**
 * A person files and follows a complaint (fs-06 section 5, n5_grievances): topic first, words next, one ladder with the
 * claims officer as the active step and the outside steps honest about being SIMULATED or self-filed, a second filing
 * on the same payout returns the open one, and Mark as solved closes it. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-grievance`.
 */
import { expect, test } from '@playwright/test'

import { anilAt1705, APP, expectCleanScreen, goWithin, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp') || !has('n5_grievances'), 'needs n1_miniapp and n5_grievances')
test.use({ viewport: { width: 390, height: 844 } })

test('with nothing filed the screen says so and offers one New complaint button', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=grievances`)
  await expect(page.getByTestId('screen-grievances')).toBeVisible()
  await expect(page.getByTestId('grv-card')).toHaveCount(0)
  await expect(page.getByTestId('grv-new').first()).toBeVisible()
  await expectCleanScreen(page)
  expect(errors).toEqual([])
})

test('a complaint needs a topic and words; filing it shows the ladder, the case and the SIMULATED outside steps', async ({ page }) => {
  const errors = guardErrors(page)
  await anilAt1705(page)
  await goWithin(page, `${APP}?lang=en&screen=grievances`)
  await page.getByTestId('grv-new').first().click()
  await expect(page.getByTestId('grv-send')).toBeDisabled()
  await page.getByTestId('grv-topic-PAYOUT_AMOUNT').click()
  await expect(page.getByTestId('grv-send')).toBeDisabled()
  await page.getByTestId('grv-text').fill('x'.repeat(501))
  await expect(page.getByTestId('grv-text')).toHaveValue('x'.repeat(500))
  await page.getByTestId('grv-text').fill('   ')
  await expect(page.getByTestId('grv-send')).toBeDisabled()
  await page.getByTestId('grv-text').fill('The amount looks low to me')
  await expect(page.getByTestId('grv-send')).toBeEnabled()
  await page.getByTestId('grv-send').click()

  const card = page.getByTestId('grv-card')
  await expect(card).toHaveCount(1)
  await expect(card).toContainText(/case C-\d+/i)
  await expect(page.getByTestId('grv-step-PAYTM_DISPUTE')).toHaveAttribute('aria-current', 'step')
  await expect(page.getByTestId('grv-clock-PAYTM_DISPUTE')).toContainText('24 hours')
  await expect(page.getByTestId('grv-escalate-PAYTM_DISPUTE')).toHaveCount(0)
  for (const outside of ['INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN']) {
    await expect(page.getByTestId(`grv-step-${outside}`)).toHaveAttribute('data-state', 'NOT_STARTED')
  }
  await expect(page.getByTestId('grv-delivery-INSURER_GRO')).toContainText('SIMULATED')
  await expect(page.getByTestId('grv-delivery-BIMA_BHAROSA')).toContainText('yourself')
  await expect(page.getByTestId('grv-outside')).toContainText('nothing is sent')

  await page.getByTestId('grv-new').first().click()
  await page.getByTestId('grv-topic-PAYOUT_AMOUNT').click()
  await page.getByTestId('grv-text').fill('Same thing again')
  await page.getByTestId('grv-send').click()
  await expect(page.getByTestId('grv-card')).toHaveCount(1)

  await page.getByTestId('grv-resolve-PAYTM_DISPUTE').click()
  await expect(page.getByTestId('grv-card')).toHaveAttribute('data-status', 'RESOLVED')
  expect(errors).toEqual([])
})

test('a payout complaint before any payout is refused in plain words and nothing is filed', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=grievances`)
  await page.getByTestId('grv-new').first().click()
  await page.getByTestId('grv-topic-PAYOUT_AMOUNT').click()
  await page.getByTestId('grv-text').fill('The amount looks low')
  await page.getByTestId('grv-send').click()
  await expect(page.getByTestId('grv-card')).toHaveCount(0)
  await expect(page.getByTestId('screen-grievances')).not.toContainText(/undefined|\[object/)
})

test('Hindi and Marathi ladders draw their own words', async ({ page }) => {
  await anilAt1705(page)
  for (const lang of has('n8_marathi') ? ['hi', 'mr'] : ['hi']) {
    await goWithin(page, `${APP}?lang=${lang}&screen=grievances`)
    await expect(page.getByTestId('screen-grievances')).toBeVisible()
    await page.getByTestId('grv-new').first().click()
    await expect(page.getByTestId('grv-new-sheet')).toContainText(/[ऀ-ॿ]/)
    await page.getByTestId('grv-new-close').click()
    await expectCleanScreen(page)
  }
})

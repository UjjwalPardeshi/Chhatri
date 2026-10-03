/**
 * A person uses the consent centre (fs-07, n6_consents): the switch asks before it withdraws, Keep it on changes
 * nothing, Turn off writes a line to the activity log, the slip then needs the OK box again, and turning it back on
 * works; the held slip can be erased once its claim is answered. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-consents`.
 */
import { expect, test } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'
import { APP, expectCleanScreen, goWithin, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp') || !has('n6_consents'), 'needs n1_miniapp and n6_consents')
test.use({ viewport: { width: 390, height: 844 } })

const SLIP_SWITCH = 'switch-SLIP_DATA_FOR_HOSPITAL_CLAIM'

test('the three consents are on and marked SIMULATED; Keep it on changes nothing', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=consents`)
  for (const purpose of ['SALES_DATA_FOR_CLAIM', 'SLIP_DATA_FOR_HOSPITAL_CLAIM', 'SETTLEMENT_DEDUCTION']) {
    await expect(page.getByTestId(`consent-${purpose}`)).toHaveAttribute('data-status', 'ACTIVE')
    await expect(page.getByTestId(`consent-${purpose}`).getByTestId('consent-simulated')).toBeVisible()
  }
  await page.getByTestId(SLIP_SWITCH).click()
  await expect(page.getByTestId('withdraw-effect')).toContainText('stops reading slips')
  await page.getByTestId('withdraw-sheet-keep').click()
  await expect(page.getByTestId('withdraw-sheet')).toHaveCount(0)
  await expect(page.getByTestId('consent-SLIP_DATA_FOR_HOSPITAL_CLAIM')).toHaveAttribute('data-status', 'ACTIVE')
  await expectCleanScreen(page)
  expect(errors).toEqual([])
})

test('Escape closes the withdraw sheet without withdrawing', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=consents`)
  await page.getByTestId(SLIP_SWITCH).click()
  await expect(page.getByTestId('withdraw-sheet')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('withdraw-sheet')).toHaveCount(0)
  await expect(page.getByTestId('consent-SLIP_DATA_FOR_HOSPITAL_CLAIM')).toHaveAttribute('data-status', 'ACTIVE')
})

test('withdrawing the slip consent is logged, the slip screen asks for the OK again, and turning it on restores it', async ({ page }) => {
  test.skip(!has('n3_slip_precheck'), 'needs n3_slip_precheck for the slip screen')
  const errors = guardErrors(page)
  await openConsole(page)
  await loadScenario(page, 'illness', 'illness replay')
  await seek(page, '11:20')
  await goWithin(page, `${APP}?lang=en&screen=consents`)
  await page.getByTestId(SLIP_SWITCH).click()
  await page.getByTestId('withdraw-sheet-confirm').click()
  await expect(page.getByTestId('withdraw-sheet')).toHaveCount(0)
  const card = page.getByTestId('consent-SLIP_DATA_FOR_HOSPITAL_CLAIM')
  await expect(card).toHaveAttribute('data-status', 'WITHDRAWN')
  await expect(card.getByTestId('consent-regrant')).toBeVisible()

  await page.getByTestId('consent-activity-link').click()
  await expect(page.getByTestId('screen-consent-activity')).toBeVisible()
  await expect(page.getByTestId('activity-row').first()).toHaveAttribute('data-kind', /WITHDRAW/)
  await page.getByTestId('activity-check').click()
  await expect(page.getByTestId('activity-check-result')).toContainText(/checks out.*none changed/i)

  await goWithin(page, `${APP}?lang=en&screen=slip`)
  await expect(page.getByTestId('slip-consent')).toBeVisible()
  await expect(page.getByTestId('slip-demo-good')).toBeDisabled()
  await page.getByTestId('slip-consent').check()
  await expect(page.getByTestId('slip-demo-good')).toBeEnabled()
  await page.getByTestId('slip-demo-good').click()
  await expect(page.getByTestId('slip-result')).toHaveAttribute('data-status', 'READY')

  await goWithin(page, `${APP}?lang=en&screen=consents`)
  await expect(page.getByTestId('consent-SLIP_DATA_FOR_HOSPITAL_CLAIM')).toHaveAttribute('data-status', 'ACTIVE')
  expect(errors).toEqual([])
})

test('Hindi and Marathi consent centres draw their own words', async ({ page }) => {
  for (const lang of has('n8_marathi') ? ['hi', 'mr'] : ['hi']) {
    await page.goto(`${APP}?lang=${lang}&screen=consents`)
    await expect(page.getByTestId('screen-consents')).toBeVisible()
    await page.getByTestId(SLIP_SWITCH).click()
    await expect(page.getByTestId('withdraw-effect')).toContainText(/[ऀ-ॿ]/)
    await page.getByTestId('withdraw-sheet-keep').click()
    await expectCleanScreen(page)
  }
})

test('forget my slip: a slip under review cannot be erased; once the officer answers it can, after asking first', async ({ page }) => {
  test.skip(!has('n3_slip_precheck'), 'needs n3_slip_precheck')
  const errors = guardErrors(page)
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:20')
  await goWithin(page, `${APP}?lang=en&screen=slip`)
  await page.getByTestId('slip-demo-good').click()
  await page.getByTestId('slip-result').waitFor()
  await (await page.getByTestId('slip-confirm').count() > 0 ? page.getByTestId('slip-confirm') : page.getByTestId('slip-team')).click()
  /** A confirmed slip is followed by the doctor question; No keeps the claim with a person, as this test needs. */
  const declineDoctor = page.getByTestId('slip-consent-no')
  await Promise.race([declineDoctor.waitFor(), page.waitForURL(/screen=claim&claim=/)])
  if ((await declineDoctor.count()) > 0) await declineDoctor.click()
  await expect(page).toHaveURL(/screen=claim&claim=/)
  await goWithin(page, `${APP}?lang=en&screen=consents`)
  const held = page.getByTestId('consent-held').locator('li').first()
  await expect(held).toHaveAttribute('data-state', 'HELD')
  await expect(held.getByRole('button', { name: 'Erase this slip' })).toBeDisabled()
  await expect(held).toContainText('still being checked')

  await page.setViewportSize({ width: 1280, height: 720 })
  await goWithin(page, '/claims')
  await page.getByRole('article', { name: /^Case C-/ }).getByRole('button', { name: 'Approve' }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await goWithin(page, `${APP}?lang=en&screen=consents`)
  const erase = page.getByTestId('consent-held').locator('li').first().getByRole('button', { name: 'Erase this slip' })
  await expect(erase).toBeEnabled()
  await erase.click()
  await expect(page.getByTestId('erase-sheet')).toContainText('activity log')
  await page.getByTestId('erase-sheet-keep').click()
  await expect(page.getByTestId('consent-held').locator('li').first()).toHaveAttribute('data-state', 'HELD')
  await erase.click()
  await page.getByTestId('erase-sheet-confirm').click()
  await expect(page.getByTestId('consent-held').locator('li').first()).toHaveAttribute('data-state', 'ERASED')
  expect(errors).toEqual([])
})

/**
 * A person reads Home, the coverage explainer and the jargon lens, then buys cover with the consent boxes
 * (fs-04 AC-9 to AC-17, fs-07 9.5). `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-cover`.
 */
import { expect, test } from '@playwright/test'

import { loadScenario, openConsole } from './helpers'
import { APP, expectCleanScreen, goWithin, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp'), 'needs n1_miniapp')
test.use({ viewport: { width: 390, height: 844 } })

test('Home shows Anil, his area and honest cover figures, then opens Coverage by tapping', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en`)
  await expect(page.getByTestId('home-greeting')).toContainText('Anil ji')
  await expect(page.getByTestId('screen-home')).toContainText('Active')
  await page.getByTestId('home-open-coverage').click()
  await expect(page.getByTestId('screen-coverage')).toBeVisible()
  await expect(page).toHaveURL(/screen=coverage/)
  await page.goBack()
  await expect(page.getByTestId('screen-home')).toBeVisible()
  await expectCleanScreen(page)
  expect(errors).toEqual([])
})

test('Coverage: numbers, jargon lens opens, closes with Escape and returns focus, section deep link opens', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=coverage`)
  await expect(page.getByTestId('coverage-numbers')).toContainText('50%')
  await expect(page.getByTestId('coverage-example-c2')).toContainText('₹1,380')
  const term = page.getByTestId('term-waiting_period').first()
  await term.click()
  const sheet = page.getByTestId('jargon-sheet')
  await expect(sheet).toBeVisible()
  await expect(sheet).toContainText('Waiting period')
  await expect(page.getByTestId('jargon-sheet-example')).toContainText('25 August')
  await expect(page.getByTestId('jargon-sheet-other')).toContainText('वेटिंग पीरियड')
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  await expect(term).toBeFocused()
  await page.goto(`${APP}?lang=en&screen=coverage#c6`)
  await expect(page.getByTestId('coverage-section-c6').getByText(/first payment covers/i).first()).toBeVisible()
  expect(errors).toEqual([])
})

test('Coverage: the jargon lens speaks Hindi and Marathi', async ({ page }) => {
  await page.goto(`${APP}?lang=hi&screen=coverage`)
  await page.getByTestId('term-waiting_period').first().click()
  await expect(page.getByTestId('jargon-sheet')).toContainText('वेटिंग पीरियड')
  await page.getByTestId('jargon-sheet-close').click()
  await expect(page.getByTestId('jargon-sheet')).toHaveCount(0)
  await expectCleanScreen(page)
})

test.describe('Get cover for a merchant who already has cover', () => {
  test('shows the status card and no way to buy twice', async ({ page }) => {
    const errors = guardErrors(page)
    await page.goto(`${APP}?lang=en&screen=buy`)
    await expect(page.getByTestId('screen-buy')).toBeVisible()
    await expect(page.getByTestId('buy-check')).toHaveCount(0)
    await expect(page.getByTestId('screen-buy')).toContainText('Active')
    expect(errors).toEqual([])
  })
})

test.describe('Get cover with a merchant who has none (S-0907, buy_cover replay)', () => {
  test.skip(!has('n6_consents'), 'needs n6_consents')
  test('check stays disabled until the two required boxes are ticked; the optional box is not needed', async ({ page }) => {
    const errors = guardErrors(page)
    await page.goto('/')
    await page.goto(`/merchant/S-0907/app?lang=en&screen=buy`)
    await expect(page.getByTestId('screen-buy')).toBeVisible()
    const check = page.getByTestId('buy-check')
    if ((await check.count()) === 0) test.skip(true, 'S-0907 already has cover without the replay loaded')
    await expect(check).toBeDisabled()
    await expect(page.getByTestId('buy-consent-hint')).toBeVisible()
    await page.getByTestId('buy-consent-SALES_DATA_FOR_CLAIM').check()
    await expect(check).toBeDisabled()
    await page.getByTestId('buy-consent-SETTLEMENT_DEDUCTION').check()
    await expect(check).toBeEnabled()
    await page.getByTestId('buy-consent-SETTLEMENT_DEDUCTION').uncheck()
    await expect(check).toBeDisabled()
    expect(errors).toEqual([])
  })
})

for (const lang of ['hi', 'mr']) {
  test(`buy in ${lang}: double clicks on the check and on Simulate payment do no harm, the truth is shown, no raw keys`, async ({ page }) => {
    test.skip(lang === 'mr' && !has('n8_marathi'), 'needs n8_marathi')
    const errors = guardErrors(page)
    await openConsole(page)
    await loadScenario(page, 'buy_cover', 'buy cover replay')
    await goWithin(page, `/merchant/S-0907/app?lang=${lang}&screen=buy`)
    if (has('n6_consents')) {
      await page.getByTestId('buy-consent-SALES_DATA_FOR_CLAIM').check()
      await page.getByTestId('buy-consent-SETTLEMENT_DEDUCTION').check()
    }
    await page.getByTestId('buy-check').dblclick()
    await expect(page.getByTestId('buy-result')).toHaveAttribute('data-outcome', 'BLOCKED', { timeout: 30_000 })
    await expect(page.getByTestId('buy-starts-on')).toContainText('25')
    await expect(page.getByTestId('buy-link-mode')).toContainText('SIMULATED')
    await expectCleanScreen(page)
    await page.getByTestId('buy-simulate-pay').dblclick()
    await expect(page.getByTestId('buy-paid')).toBeVisible()
    await expectCleanScreen(page)
    expect(errors).toEqual([])
  })
}

/**
 * A person finds help, switches language, loses the connection and follows a bad link (fs-04 sections 4, 6.3, 13). Help rows
 * follow the flags; Hindi, Marathi and English switch the tabs and the URL; offline shows a banner with the data time;
 * a failed load has Try again; an unknown merchant or claim id says so; Back works. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-help-lang`.
 */
import { expect, test } from '@playwright/test'

import { APP, expectCleanScreen, guardErrors, has, outage } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp'), 'needs n1_miniapp')
test.use({ viewport: { width: 390, height: 844 } })

const ROWS: readonly [string, string][] = [
  ['help-ask', 'n2_ask_chhatri'],
  ['help-grievances', 'n5_grievances'],
  ['help-consents', 'n6_consents'],
  ['help-slip', 'n3_slip_precheck'],
]

test('Help lists exactly the rows whose flags are on, labels the SIMULATED/FALLBACK/LIVE words, and opens the jargon lens', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=help`)
  await expect(page.getByTestId('help-coverage')).toBeVisible()
  await expect(page.getByTestId('help-language')).toBeVisible()
  for (const [row, flag] of ROWS) await expect(page.getByTestId(row)).toHaveCount(has(flag) ? 1 : 0)
  for (const mode of ['SIMULATED', 'FALLBACK', 'LIVE']) await expect(page.getByTestId(`help-mode-${mode}`)).toBeVisible()
  await expect(page.getByTestId('help-about')).toContainText('synthetic')
  await page.getByTestId('term-kyc').click()
  await expect(page.getByTestId('jargon-sheet')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('jargon-sheet')).toHaveCount(0)
  await expectCleanScreen(page)
  expect(errors).toEqual([])
})

test('every Help row opens its screen and Back returns to Help', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=help`)
  const rows = ['help-coverage', ...ROWS.filter(([, flag]) => has(flag)).map(([row]) => row), 'help-language']
  for (const row of rows) {
    await page.getByTestId(row).click()
    await expect(page.getByTestId('screen-help')).toHaveCount(0)
    await page.goBack()
    await expect(page.getByTestId('screen-help')).toBeVisible()
  }
})

test('language: English to Hindi to Marathi (when on) and back, the tabs and the URL follow, and a reload keeps it', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=settings`)
  await page.getByTestId('lang-option-hi').click()
  await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'hi')
  await expect(page).toHaveURL(/lang=hi/)
  await expect(page.getByTestId('app-tab-home')).toContainText('होम')
  if (has('n8_marathi')) {
    await page.getByTestId('lang-option-mr').click()
    await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'mr')
    await expect(page.getByTestId('app-tab-home')).toContainText(/मुख्य|होम/)
    await expect(page.getByTestId('lang-preview')).toContainText(/[ऀ-ॿ]/)
    await page.reload()
    await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'mr')
  } else {
    await expect(page.getByTestId('lang-option-mr')).toHaveCount(0)
  }
  await page.getByTestId('lang-option-en').click()
  await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'en')
  await expect(page.getByTestId('app-tab-claims')).toContainText('Claims')
  expect(errors).toEqual([])
})

test('offline: Home keeps its data, shows the banner, and recovers when the connection returns', async ({ page, context }) => {
  await page.goto(`${APP}?lang=en`)
  await expect(page.getByTestId('home-greeting')).toContainText('Anil ji')
  await context.setOffline(true)
  await expect(page.getByTestId('app-offline-banner')).toContainText(/Offline/)
  await expect(page.getByTestId('home-greeting')).toContainText('Anil ji')
  await page.getByTestId('app-tab-help').click()
  await expect(page.getByTestId('screen-help')).toBeVisible()
  await context.setOffline(false)
  await expect(page.getByTestId('app-offline-banner')).toHaveCount(0)
})

test('a lost connection on first load shows an error with Try again, and it recovers', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=claims`)
  await expect(page.getByTestId('screen-claims')).toBeVisible()
  await outage(page, 2500)
  await page.getByTestId('app-tab-home').click()
  await expect(page.getByTestId('app-error').first()).toContainText('cannot connect')
  await expect(page.getByTestId('app-offline-banner')).toHaveCount(0)
  await expect.poll(async () => { await page.getByTestId('app-error-retry').first().click({ timeout: 500 }).catch(() => undefined); return page.getByTestId('app-error').count() }, { timeout: 12_000 }).toBe(0)
  await expect(page.getByTestId('home-greeting')).toBeVisible()
})

test('an unknown merchant, a malformed claim id and an unknown screen are met with words, not a crash', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto('/merchant/S-9999/app?lang=en')
  await expect(page.getByTestId('app-root')).toContainText('could not find')
  await page.goto(`${APP}?lang=en&screen=claim&claim=banana`)
  await expect(page.getByTestId('app-root')).toBeVisible()
  await expect(page.getByTestId('app-root')).not.toContainText(/undefined|\[object/)
  await page.goto(`${APP}?lang=en&screen=nonsense`)
  await expect(page.getByTestId('screen-home')).toBeVisible()
  await page.goto(`${APP}?lang=zz`)
  await expect(page.getByTestId('screen-home')).toBeVisible()
  expect(errors.filter((e) => !/404|Failed to load resource/.test(e))).toEqual([])
})

test('keyboard: the tabs are reachable with Tab and activated with Enter', async ({ page }) => {
  await page.goto(`${APP}?lang=en`)
  await page.getByTestId('app-tab-home').focus()
  await page.keyboard.press('Tab')
  await expect(page.getByTestId('app-tab-claims')).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('screen-claims')).toBeVisible()
  await page.getByTestId('app-tab-help').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('screen-help')).toBeVisible()
})

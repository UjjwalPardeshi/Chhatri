/**
 * A person opens every mini-app screen by deep link in English, Hindi and Marathi (card: QA sweep). Each screen must
 * draw, show no raw copy key and no sideways scroll, and raise no console error. Screens behind a flag that is off
 * must fall back to Home. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-screens`.
 */
import { expect, test } from '@playwright/test'

import { APP, expectCleanScreen, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp'), 'needs n1_miniapp')
test.use({ viewport: { width: 390, height: 844 } })

const SCREENS: readonly { screen: string; flag: string | null }[] = [
  { screen: 'home', flag: null },
  { screen: 'coverage', flag: null },
  { screen: 'buy', flag: null },
  { screen: 'claims', flag: null },
  { screen: 'help', flag: null },
  { screen: 'settings', flag: null },
  { screen: 'ask', flag: 'n2_ask_chhatri' },
  { screen: 'slip', flag: 'n3_slip_precheck' },
  { screen: 'grievances', flag: 'n5_grievances' },
  { screen: 'consents', flag: 'n6_consents' },
  { screen: 'consent-activity', flag: 'n6_consents' },
]
const LANGS = has('n8_marathi') ? ['en', 'hi', 'mr'] : ['en', 'hi']

for (const lang of LANGS) {
  for (const { screen, flag } of SCREENS) {
    test(`${screen} in ${lang} ${flag && !has(flag) ? 'falls back to Home (flag off)' : 'draws cleanly'}`, async ({ page }) => {
      const errors = guardErrors(page)
      await page.goto(`${APP}?screen=${screen}&lang=${lang}`)
      await expect(page.getByTestId('app-root')).toHaveAttribute('lang', lang)
      await expect(page.getByTestId(flag && !has(flag) ? 'screen-home' : `screen-${screen}`)).toBeVisible()
      await expect(page.getByTestId('app-skeleton')).toHaveCount(0)
      await expectCleanScreen(page)
      expect(errors).toEqual([])
    })
  }
}

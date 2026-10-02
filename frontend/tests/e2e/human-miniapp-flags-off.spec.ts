/**
 * With n1_miniapp off the app does not exist: its route goes back to the merchant page, the phone frame is not drawn
 * and no mini-app code is asked for; with it on but a feature flag off, that feature's entry points are absent from Home.
 * `E2E_FEATURES= npx playwright test --project=mock human-miniapp-flags-off` (all off), or n1_miniapp alone.
 */
import { expect, test } from '@playwright/test'

import { APP, guardErrors, has } from './human-miniapp-helpers'

test.use({ viewport: { width: 1280, height: 720 } })

test('flag off: /app goes back to the merchant page, no frame, no mini-app chunk', async ({ page }) => {
  test.skip(has('n1_miniapp'), 'only when n1_miniapp is off')
  const errors = guardErrors(page)
  const chunks: string[] = []
  page.on('request', (request) => {
    if (/miniapp\/(shell|screens|components)\//.test(new URL(request.url()).pathname) && /\.(tsx?|js)(\?|$)/.test(request.url())) chunks.push(request.url())
  })
  await page.goto(`${APP}?lang=hi`)
  await expect(page).toHaveURL(/\/merchant\/S-0142(\?|$)/)
  await expect(page.locator('.clock-label')).toContainText('Mumbai')
  await expect(page.getByTestId('app-frame')).toHaveCount(0)
  await expect(page.getByTestId('app-root')).toHaveCount(0)
  expect(chunks).toEqual([])
  expect(errors).toEqual([])
})

test('flag on: Home offers Ask only with n2_ask_chhatri and the slip row only with n3_slip_precheck', async ({ page }) => {
  test.skip(!has('n1_miniapp'), 'needs n1_miniapp')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${APP}?lang=en`)
  await expect(page.getByTestId('screen-home')).toBeVisible()
  await expect(page.getByTestId('home-open-ask')).toHaveCount(has('n2_ask_chhatri') ? 1 : 0)
  await page.getByTestId('app-tab-help').click()
  await expect(page.getByTestId('help-slip')).toHaveCount(has('n3_slip_precheck') ? 1 : 0)
})

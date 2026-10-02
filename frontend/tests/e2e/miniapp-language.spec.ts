/**
 * S9 Language (fs-04 AC-32, AC-34, card 3.11): Hindi to English from the Help tab, the tabs and the URL follow, and
 * Marathi is not offered while n8_marathi is off. Run with `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-language`.
 */
import { expect, test } from '@playwright/test'

const FEATURES = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim())
test.skip(!FEATURES.includes('n1_miniapp'), 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

test.use({ viewport: { width: 390, height: 844 } })

test('switches from Hindi to English through Help and Language', async ({ page }) => {
  await page.goto('/merchant/S-0142/app?lang=hi')
  await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'hi')
  await page.getByTestId('app-tab-help').click()
  await page.getByTestId('help-language').click()
  await expect(page.getByTestId('screen-language')).toBeVisible()
  if (!FEATURES.includes('n8_marathi')) await expect(page.getByTestId('lang-option-mr')).toHaveCount(0)
  await page.getByTestId('lang-option-en').click()
  await expect(page.getByTestId('app-root')).toHaveAttribute('lang', 'en')
  await expect(page.getByTestId('app-tab-home')).toContainText('Home')
  await expect(page.getByTestId('app-tab-claims')).toContainText('Claims')
  await expect(page.getByTestId('app-tab-help')).toContainText('Help')
  await expect(page).toHaveURL(/lang=en/)
})

/**
 * The receipt on paper (fs-04 AC-30, 10.5, card 3.10): "Print or save as PDF" calls window.print once, the bars and
 * the buttons are hidden in print media, the print header reads "Chhatri · decision receipt · prototype · SIMULATED
 * data", and the whole receipt comes out on one A4 page. Run with
 * `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-receipt-print`.
 */
import { expect, test, type Page } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')
test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

const PRINT_COUNT = '__printCalls'

/** A client-side move to a route, so the mock backend keeps the loaded scenario. */
async function goWithin(page: Page, href: string): Promise<void> {
  await page.evaluate((to) => {
    window.history.pushState({}, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, href)
}

/** The number of pages of a PDF: its page objects, not the page tree. */
const pagesOf = (pdf: Buffer): number => (pdf.toString('latin1').match(/\/Type\s*\/Page(?![s\w])/g) ?? []).length

async function openAnilsReceipt(page: Page): Promise<void> {
  await page.setViewportSize({ width: 390, height: 844 })
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')
  await goWithin(page, '/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142')
  await expect(page.getByTestId('receipt-decision-id')).toHaveText('D-000142')
}

test('receipt print: one call to window.print, the bars hidden in print, one page', async ({ page }) => {
  await openAnilsReceipt(page)
  await page.evaluate((key) => {
    Reflect.set(window, key, 0)
    window.print = () => void Reflect.set(window, key, Number(Reflect.get(window, key)) + 1)
  }, PRINT_COUNT)
  await page.getByTestId('receipt-print').click()
  expect(await page.evaluate((key) => Reflect.get(window, key), PRINT_COUNT)).toBe(1)

  await page.emulateMedia({ media: 'print' })
  await expect(page.getByTestId('app-tabbar')).toBeHidden()
  await expect(page.getByTestId('app-nba')).toBeHidden()
  await expect(page.getByTestId('app-appbar')).toBeHidden()
  await expect(page.getByTestId('receipt-print')).toBeHidden()
  await expect(page.getByTestId('receipt-check-log')).toBeHidden()
  await expect(page.getByTestId('receipt-print-header')).toBeVisible()
  await expect(page.getByTestId('receipt-print-header')).toHaveText('Chhatri · decision receipt · prototype · SIMULATED data')
  await expect(page.getByTestId('receipt-checks')).toContainText('All 9 checks passed.')
  await expect(page.getByTestId('receipt-grievance-path')).toBeVisible()

  const pdf = await page.pdf({ format: 'A4', printBackground: true, margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' } })
  expect(pagesOf(pdf)).toBe(1)
  await page.emulateMedia({ media: null })
  await expect(page.getByTestId('app-tabbar')).toBeVisible()
  await expect(page.getByTestId('receipt-print-header')).toBeHidden()
})

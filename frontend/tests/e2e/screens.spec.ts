/**
 * Key-moment screenshots of every page against the real backend (SPEC §20 "works at 1280×720
 * (projector) and on phones"): saved to test-results/screens/ for review before the demo. Runs only
 * in the live project (CONSOLE_URL); each shot waits for the moment it shows, so a missing number
 * fails the run instead of producing a wrong picture.
 */
import { expect, test, type Page } from '@playwright/test'

import { bubble, goTo, IS_MOCK, LINES, loadScenario, openConsole, SCREENS_DIR, seek, settled } from './helpers'

test.skip(IS_MOCK, 'screenshots are taken against the real backend (npm run test:e2e)')
test.describe.configure({ timeout: 180_000 })

const PHONE = { width: 390, height: 844 }

async function shot(page: Page, name: string): Promise<void> {
  await settled(page)
  await page.screenshot({ path: `${SCREENS_DIR}/${name}.png` })
}

async function step(page: Page, label: string): Promise<void> {
  await page.getByRole('button', { name: label, exact: true }).click()
  await expect(page.getByRole('button', { name: label, exact: true })).toBeEnabled()
}

test('projector 1280×720: the overview and the storm on the live map', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: /Chhatri/ })).toBeVisible()
  await expect(page.locator('.ov-hero__phone .soundbox')).toBeVisible()
  await page.waitForTimeout(2_200)
  await shot(page, '01-overview-hero')

  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay · 08:00')
  await shot(page, '02-live-0800-loaded')
  await seek(page, '15:30')
  await expect(page.getByRole('region', { name: 'Zone Z7' }).getByText('Watching')).toBeVisible()
  await shot(page, '03-live-1530-watching')
  await seek(page, '17:03')
  await step(page, '+1 min')
  await expect(page.locator('.toast')).toContainText('₹1,380 credited · 17:04')
  await shot(page, '04-live-1704-credited')
  await seek(page, '17:10')
  await expect(page.locator('.explanation[data-zone="Z9"]')).toBeVisible()
  await shot(page, '05-live-1710-storm')
})

test('projector 1280×720: Anil’s phone, the why answer, the dispute and case C-2291', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'monsoon', 'monsoon replay')
  await seek(page, '17:05')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await expect(bubble(phone, LINES.paused)).toBeVisible()
  await shot(page, '06-phone-1705-paid')
  await phone.getByRole('button', { name: /मुझे इतने ही पैसे क्यों मिले/ }).click()
  await expect(bubble(phone, LINES.explain)).toBeVisible()
  await shot(page, '07-phone-why')
  await phone.getByRole('button', { name: /मेरा नुकसान ज़्यादा हुआ/ }).click()
  await expect(phone.getByRole('link', { name: /C-2291/ })).toBeVisible()
  await shot(page, '08-phone-dispute')
  await phone.getByRole('link', { name: /C-2291/ }).click()
  await expect(page.getByRole('article', { name: 'Case C-2291' })).toBeVisible()
  await shot(page, '09-claims-dispute')
})

test('projector 1280×720: the slip mismatch, the officer approval and the illness payout', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:25')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: 'Slip with a different name' }).click()
  await expect(bubble(phone, LINES.slipToHuman)).toBeVisible()
  await shot(page, '10-phone-slip-to-human')
  await goTo(page, 'Claims')
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await expect(detail.getByText('REFERRED', { exact: true })).toBeVisible()
  await shot(page, '11-claims-referred')
  await detail.getByRole('button', { name: 'Approve' }).click()
  await expect(detail.locator('.resolution')).toContainText('₹1,500 credited')
  await shot(page, '12-claims-approved')
  await detail.getByRole('link', { name: 'Open the phone' }).click()
  await expect(bubble(phone, LINES.officerApproved)).toBeVisible()
  await shot(page, '13-phone-officer-approved')

  await loadScenario(page, 'illness', 'illness replay')
  await seek(page, '11:25')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: "Anil's admission slip" }).click()
  await expect(bubble(phone, LINES.personalPaid)).toBeVisible()
  await shot(page, '14-phone-illness-paid')
})

test('projector 1280×720: blocked cover, audit, backtest and policy', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'buy_cover', 'buy cover replay')
  await seek(page, '18:10')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: 'Red alert tomorrow. Cover me today.' }).click()
  await expect(bubble(phone, LINES.coverBlocked)).toBeVisible()
  await shot(page, '15-phone-cover-blocked')
  await goTo(page, 'Audit')
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/^Chain valid/)).toBeVisible()
  await shot(page, '16-audit-verified')
  await page.locator('.integrations-summary').click()
  await expect(page.locator('.integrations-popover')).toBeVisible()
  await shot(page, '17-audit-integrations')
  await page.keyboard.press('Escape')
  await goTo(page, 'Backtest')
  await expect(page.getByText('All of them').first()).toBeVisible()
  await shot(page, '18-backtest')
  await goTo(page, 'Policy')
  await expect(page.getByText('Three live tests in our demo')).toBeVisible()
  await shot(page, '19-policy')
})

test.describe('phone 390×844', () => {
  test.use({ viewport: PHONE })

  test('the overview, the live map and Anil’s phone on a phone', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: /Chhatri/ })).toBeVisible()
    await page.waitForTimeout(1_500)
    await shot(page, '20-phone-overview')
    await openConsole(page)
    await loadScenario(page, 'monsoon', 'monsoon replay')
    await seek(page, '17:05')
    await expect(page.locator('.zone-label', { hasText: 'Z7 · 37% · 46 shops' })).toBeVisible()
    await shot(page, '21-phone-live-1705')
    await goTo(page, 'Merchant phone')
    const phone = page.getByTestId('phone')
    await expect(bubble(phone, LINES.paused)).toBeVisible()
    await shot(page, '22-phone-merchant-1705')
    await goTo(page, 'Claims')
    await expect(page.getByRole('heading', { name: 'Claims queue' })).toBeVisible()
    await shot(page, '23-phone-claims')
  })
})

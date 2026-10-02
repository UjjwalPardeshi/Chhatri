/**
 * A person sends a hospital slip from the mini-app (fs-02 7.3, n3_slip_precheck): the good demo slip is read and
 * confirmed into a claim; a blurry one gets a plain next step; the third photo is the last (send to the team);
 * sending to the team opens a case; with no check-in open the app says so instead of failing silently; offline blocks.
 * `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-slip`.
 */
import { expect, test, type Page } from '@playwright/test'

import { loadScenario, openConsole, seek } from './helpers'
import { goWithin, guardErrors, has, expectCleanScreen } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp') || !has('n3_slip_precheck'), 'needs n1_miniapp and n3_slip_precheck')
test.use({ viewport: { width: 390, height: 844 } })

const SLIP = '/merchant/S-0142/app?lang=en&screen=slip'
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64')

async function silentDay(page: Page): Promise<void> {
  await openConsole(page)
  await loadScenario(page, 'illness', 'illness replay')
  await seek(page, '11:20')
  await goWithin(page, SLIP)
  await expect(page.getByTestId('screen-slip')).toBeVisible()
}

async function tickIfAsked(page: Page): Promise<void> {
  if ((await page.getByTestId('slip-consent').count()) > 0) await page.getByTestId('slip-consent').check()
}

test('the good demo slip is read, shown plainly, and confirming it opens the paid claim', async ({ page }) => {
  const errors = guardErrors(page)
  await silentDay(page)
  await tickIfAsked(page)
  await page.getByTestId('slip-demo-good').click()
  await expect(page.getByTestId('slip-result')).toHaveAttribute('data-status', 'READY')
  await expect(page.getByTestId('slip-fields')).toContainText('Anil R. Jadhav')
  await expect(page.getByTestId('slip-fields')).toContainText('KEM Hospital, Parel')
  await expect(page.getByTestId('slip-footer')).toContainText('SIMULATED')
  await expect(page.getByTestId('screen-slip')).not.toContainText(/confidence|\d+\s?%/i)
  await expectCleanScreen(page)
  await page.getByTestId('slip-confirm').click()
  await expect(page).toHaveURL(/screen=claim&claim=CL-\d+/)
  await expect(page.getByTestId('claim-amount')).toContainText('₹1,500')
  expect(errors).toEqual([])
})

test('a blurry slip gets a plain sentence, a retake works, and the third photo can only go to the team', async ({ page }) => {
  await silentDay(page)
  await tickIfAsked(page)
  await page.getByTestId('slip-demo-blurry').click()
  await expect(page.getByTestId('slip-guidance')).toContainText('not clear')
  await expect(page.getByTestId('slip-confirm')).toHaveCount(0)
  for (let photo = 2; photo <= 3; photo += 1) {
    const chooser = page.waitForEvent('filechooser')
    await page.getByTestId('slip-retake').click()
    await (await chooser).setFiles({ name: `photo${photo}.png`, mimeType: 'image/png', buffer: PNG })
    await expect(page.getByTestId('slip-result')).toHaveAttribute('data-attempt', String(photo))
  }
  await expect(page.getByTestId('slip-guidance')).toContainText(/team/i)
  await expect(page.getByTestId('slip-retake')).toHaveCount(0)
  await page.getByTestId('slip-team').click()
  await expect(page).toHaveURL(/screen=claim&claim=CL-\d+/)
  await expect(page.getByTestId('claim-case-chip')).toContainText(/case C-\d+/)
})

test('with no check-in open the app explains and stays usable', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(SLIP)
  await expect(page.getByTestId('screen-slip')).toBeVisible()
  await tickIfAsked(page)
  await page.getByTestId('slip-demo-good').click()
  await expect(page.getByTestId('slip-error')).toBeVisible()
  await expect(page.getByTestId('slip-demo-good')).toBeEnabled()
  expect(errors.filter((e) => !/409|Failed to load resource/.test(e))).toEqual([])
})

test('offline: the photo buttons are off and say why', async ({ page, context }) => {
  await page.goto(SLIP)
  await expect(page.getByTestId('screen-slip')).toBeVisible()
  await context.setOffline(true)
  await expect(page.getByTestId('slip-take')).toBeDisabled()
  await expect(page.getByTestId('slip-gallery')).toBeDisabled()
  await expect(page.getByTestId('slip-demo-good')).toBeDisabled()
  await context.setOffline(false)
  await expect(page.getByTestId('slip-take')).toBeEnabled()
})

test.describe('with n6_consents on and no slip consent given', () => {
  test.skip(!has('n6_consents'), 'needs n6_consents')
  test('the photo waits for the OK box', async ({ page }) => {
    await page.goto('/')
    await silentDay(page)
    if ((await page.getByTestId('slip-consent').count()) === 0) test.skip(true, 'Anil has the slip consent active in the demo data')
    await expect(page.getByTestId('slip-demo-good')).toBeDisabled()
    await page.getByTestId('slip-consent').check()
    await expect(page.getByTestId('slip-demo-good')).toBeEnabled()
  })
})

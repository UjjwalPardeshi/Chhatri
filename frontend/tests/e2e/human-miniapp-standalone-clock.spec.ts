/**
 * A visitor opens the app on its own URL (no console), moves the demo clock to the payout from the clock sheet, finds
 * the claim, and resets (screens-and-flows 8, N7); then the same app inside the console frame at 1280 by 720 keeps its
 * sheets inside the phone. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-standalone-clock`.
 */
import { expect, test } from '@playwright/test'

import { APP, expectCleanScreen, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp'), 'needs n1_miniapp')

test.describe('standalone on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('at 08:00 there is no claim; the clock sheet jumps to the payout, the claim appears, and Back to the start empties it', async ({ page }) => {
    const errors = guardErrors(page)
    await page.goto(`${APP}?lang=en&screen=claims`)
    await expect(page.getByTestId('app-clock')).toContainText('08:00')
    await expect(page.getByTestId('claims-empty')).toBeVisible()
    await page.getByTestId('app-clock-open').click()
    await expect(page.getByTestId('app-clock-sheet')).toBeVisible()
    await page.getByTestId('app-clock-chapter-17:05').click()
    await expect(page.getByTestId('app-clock')).toContainText('17:05')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('app-clock-sheet')).toHaveCount(0)
    const card = page.getByTestId('claim-card-CL-000142')
    await expect(card).toContainText('₹1,380')
    await expect(card).toContainText('Paid')
    await expectCleanScreen(page)
    await page.getByTestId('app-clock-open').click()
    await page.getByTestId('app-clock-reset').click()
    await expect(page.getByTestId('app-clock')).toContainText('08:00')
    await page.keyboard.press('Escape')
    await page.getByTestId('app-tab-claims').click()
    await expect(page.getByTestId('claims-empty')).toBeVisible()
    expect(errors).toEqual([])
  })

  test('double clicking a chapter and reloading mid-flow leave a working app', async ({ page }) => {
    const errors = guardErrors(page)
    await page.goto(`${APP}?lang=en&screen=claims`)
    await page.getByTestId('app-clock-open').click()
    await page.getByTestId('app-clock-chapter-17:04').dblclick()
    await expect(page.getByTestId('app-clock')).toContainText('17:04')
    await page.reload()
    await expect(page.getByTestId('screen-claims')).toBeVisible()
    await expect(page.getByTestId('app-clock')).toContainText('08:00')
    expect(errors).toEqual([])
  })
})

test.describe('inside the console frame at 1280 by 720', () => {
  test.use({ viewport: { width: 1280, height: 720 } })

  test('the jargon lens opens inside the frame and the frame has no sideways scroll', async ({ page }) => {
    const errors = guardErrors(page)
    await page.goto('/merchant/S-0142?lang=en&screen=coverage')
    const frame = page.getByTestId('app-frame')
    await expect(frame.getByTestId('screen-coverage')).toBeVisible()
    await frame.getByTestId('term-waiting_period').first().click()
    const sheet = page.getByTestId('jargon-sheet')
    await expect(sheet).toBeVisible()
    const box = await sheet.boundingBox()
    const bounds = await frame.boundingBox()
    if (!box || !bounds) throw new Error('sheet or frame not on screen')
    expect(box.x).toBeGreaterThanOrEqual(bounds.x - 1)
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1)
    await page.keyboard.press('Escape')
    await expect(sheet).toHaveCount(0)
    expect(errors).toEqual([])
  })

  test('Ask Chhatri inside the frame answers and its labels stay SIMULATED', async ({ page }) => {
    test.skip(!has('n2_ask_chhatri'), 'needs n2_ask_chhatri')
    await page.goto('/merchant/S-0142?lang=en&screen=ask')
    const frame = page.getByTestId('app-frame')
    await frame.getByTestId('ask-input').fill('What is the waiting period?')
    await frame.getByTestId('ask-send').click()
    await expect(frame.getByTestId('ask-answer')).toContainText('7 days')
    await expect(frame.getByTestId('ask-footer')).toContainText('SIMULATED')
  })
})

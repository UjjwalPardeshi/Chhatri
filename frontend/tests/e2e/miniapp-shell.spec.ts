/**
 * The mini-app shell (fs-04 sections 4 and 8, card 3.7): the frame beside the phone on the merchant page, the full
 * screen route without the console around it, the three tabs and the URL state. The app is behind the flag n1_miniapp,
 * which the console under test must have on: `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-shell`.
 * `E2E_SHOTS_DIR` saves a screenshot of each layout there, for a look by eye.
 */
import { expect, test, type Page } from '@playwright/test'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')
const SHOTS_DIR = process.env.E2E_SHOTS_DIR

test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS_DIR) await page.screenshot({ path: `${SHOTS_DIR}/${name}.png` })
}

async function box(page: Page, testId: string) {
  const found = await page.getByTestId(testId).boundingBox()
  if (!found) throw new Error(`${testId} is not on screen`)
  return found
}

test.describe('on the merchant page at 1280 by 720', () => {
  test('shows the phone, the app frame and the panel side by side, in that order', async ({ page }) => {
    await page.goto('/merchant/S-0142?lang=en')
    await expect(page.getByTestId('phone').getByText('Paytm · Chhatri')).toBeVisible()
    await expect(page.getByTestId('screen-home')).toBeVisible()
    const phone = await box(page, 'phone')
    const frame = await box(page, 'app-frame')
    const panel = await page.locator('.merchant-panel').boundingBox()
    if (!panel) throw new Error('the panel is not on screen')
    expect(phone.x + phone.width).toBeLessThanOrEqual(frame.x + 1)
    expect(frame.x + frame.width).toBeLessThanOrEqual(panel.x + 1)
    expect(Math.abs(phone.y - frame.y)).toBeLessThan(4)
    expect(Math.abs(phone.height - frame.height)).toBeLessThan(4)
    await expect(page.getByTestId('app-root')).toHaveClass(/miniapp/)
    await shot(page, 'merchant-1280')
  })

  test('stacks as the window narrows: the panel below at 1024, the frame under the phone at 700', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto('/merchant/S-0142?lang=en')
    await expect(page.getByTestId('screen-home')).toBeVisible()
    const panel = page.locator('.merchant-panel')
    await expect(panel).toBeAttached()
    const phone = await box(page, 'phone')
    const frame = await box(page, 'app-frame')
    const below = await panel.boundingBox()
    if (!below) throw new Error('the panel is not on screen')
    expect(frame.x).toBeGreaterThanOrEqual(phone.x + phone.width - 1)
    expect(below.y).toBeGreaterThanOrEqual(frame.y + frame.height - 1)
    await shot(page, 'merchant-1024')
    await page.setViewportSize({ width: 700, height: 900 })
    const narrowPhone = await box(page, 'phone')
    const narrowFrame = await box(page, 'app-frame')
    expect(narrowFrame.y).toBeGreaterThanOrEqual(narrowPhone.y + narrowPhone.height - 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
    await shot(page, 'merchant-700')
  })

  test('opens the same app full screen from the frame, with no console around it', async ({ page }) => {
    await page.goto('/merchant/S-0142?lang=en')
    await page.getByTestId('app-tab-claims').click()
    await expect(page.getByTestId('screen-claims')).toBeVisible()
    await page.getByTestId('app-open-fullscreen').click()
    await expect(page).toHaveURL(/\/merchant\/S-0142\/app\?lang=en&screen=claims$/)
    await expect(page.getByTestId('app-standalone')).toBeVisible()
    await expect(page.getByTestId('screen-claims')).toBeVisible()
    await expect(page.locator('.app')).toHaveCount(0)
  })
})

test.describe('full screen on a phone, 390 by 844', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('fills the viewport with three tabs, no console header and no sideways scroll', async ({ page }) => {
    await page.goto('/merchant/S-0142/app?lang=en')
    await expect(page.getByTestId('screen-home')).toBeVisible()
    await expect(page.locator('.app')).toHaveCount(0)
    const tabbar = await box(page, 'app-tabbar')
    expect(Math.abs(tabbar.y + tabbar.height - 844)).toBeLessThan(2)
    for (const tab of ['home', 'claims', 'help']) {
      const target = await box(page, `app-tab-${tab}`)
      expect(target.height).toBeGreaterThanOrEqual(44)
      expect(target.width).toBeGreaterThanOrEqual(44)
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    await shot(page, 'standalone-390')
  })

  test('moves between tabs by the URL, and the browser Back button returns', async ({ page }) => {
    await page.goto('/merchant/S-0142/app?lang=en')
    await expect(page.getByTestId('app-tab-home')).toHaveAttribute('aria-current', 'page')
    await page.getByTestId('app-tab-claims').click()
    await expect(page.getByTestId('screen-claims')).toBeVisible()
    await expect(page).toHaveURL(/screen=claims/)
    await expect(page.getByTestId('app-tab-claims')).toHaveAttribute('aria-current', 'page')
    await page.goBack()
    await expect(page.getByTestId('screen-home')).toBeVisible()
    await expect(page).not.toHaveURL(/screen=/)
  })
})

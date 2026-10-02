/**
 * The console under whatever flags E2E_FEATURES names (set the same list in VITE_FEATURES and CHHATRI_FEATURES): each
 * flagged control is there when its flag is on and absent when it is off, on the projector (1280x720) and on a phone
 * (390x844), with a slow network and with the network gone. Real backend (project "live").
 */
import { expect, monsoonAt, test } from './human-console-guard'
import { E2E_FEATURES, IS_MOCK, REPLAY_TIMEOUT_MS, openConsole } from './helpers'

test.skip(IS_MOCK, 'real backend only')
test.describe.configure({ timeout: 90_000 })

const on = (flag: string) => E2E_FEATURES.includes(flag)

test('flagged controls appear only with their flag', async ({ page }) => {
  await monsoonAt(page, '17:10')
  await expect(page.getByRole('button', { name: 'Present', exact: true })).toHaveCount(on('console_polish') ? 1 : 0)
  await expect(page.getByRole('region', { name: 'Operations today' })).toHaveCount(on('h8_ops_strip') ? 1 : 0)
  await expect(page.getByRole('button', { name: /What if/ })).toHaveCount(on('h24_whatif') ? 1 : 0)
  await expect(page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: 'Evals' })).toHaveCount(on('h25_evals') ? 1 : 0)
  await page.getByRole('button', { name: /simulated/ }).click()
  const switches = page.getByRole('region', { name: 'Integrations' }).getByRole('button', { name: /Force fallback/ })
  if (on('x6_provider_panel')) await expect(switches.first()).toBeVisible()
  else await expect(switches).toHaveCount(0)
  /** The golden numbers never depend on a flag. */
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-kpi="shops"] .kpi__value')).toHaveText('312')
})

test('the 17:05 instalment line follows x4_lender_request', async ({ page }) => {
  await monsoonAt(page, '17:06')
  const res = await page.request.get('/api/merchants/S-0142/messages')
  const texts = ((await res.json()) as { data: { text_en: string | null }[] }).data.map((m) => m.text_en ?? '')
  const want = on('x4_lender_request') ? /Your lender has paused tomorrow's ₹600 instalment/ : /Tomorrow's ₹600 instalment is paused/
  expect(texts.some((t) => want.test(t))).toBe(true)
})

test('direct links and the back button keep working', async ({ page }) => {
  await monsoonAt(page, '17:10')
  for (const [path, heading] of [['/audit', 'Audit log'], ['/policy', /Automatic when/], ['/backtest', /Would Chhatri have paid/]] as const) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 }).first()).toContainText(heading)
  }
  await page.goBack()
  await expect(page).toHaveURL(/\/policy$/)
  await page.goto('/nonexistent-page')
  await expect(page.getByRole('navigation', { name: 'Pages' })).toBeVisible()
})

test('phone 390x844: no sideways scroll on every page', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  for (const path of ['/', '/live', '/claims', '/audit', '/backtest', '/policy', '/merchant/S-0142']) {
    await page.goto(path)
    await expect(page.getByRole('navigation', { name: 'Pages' })).toBeVisible()
    await page.waitForLoadState('domcontentloaded')
    const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth])
    expect(sw, path).toBeLessThanOrEqual(cw)
  }
})

test('slow network: the live map still loads; offline: the console says so and recovers', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600))
    await route.continue().catch(() => undefined)
  })
  await openConsole(page)
  await expect(page.locator('.clock-label')).toContainText('Mumbai', { timeout: REPLAY_TIMEOUT_MS })
  await page.unroute('**/api/**')
  await page.route('**/api/replay/seek', (route) => route.abort())
  await page.getByRole('textbox', { name: 'Seek to time (HH:MM)' }).fill('13:00')
  await page.getByRole('button', { name: 'Seek', exact: true }).click()
  await expect(page.getByRole('alert').first()).toBeVisible()
  await page.unroute('**/api/replay/seek')
  await page.getByRole('button', { name: 'Seek', exact: true }).click()
  await expect(page.locator('.clock-label')).toContainText('13:00', { timeout: REPLAY_TIMEOUT_MS })
})

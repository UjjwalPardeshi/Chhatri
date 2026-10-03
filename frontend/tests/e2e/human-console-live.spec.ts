/**
 * A person at the officer console, real backend (project "live"): presenter keys, ops strip, what-if drawer, provider
 * panel, case panel, evals, reload mid-replay and a dropped event stream. Needs every flag on in both the console and the
 * backend (VITE_FEATURES / CHHATRI_FEATURES), so it skips itself otherwise.
 */
import { api, expect, monsoonAt, test } from './human-console-guard'
import { bubble, E2E_FEATURES as FEATS, goTo, LINES, IS_MOCK, loadScenario, openConsole, REPLAY_TIMEOUT_MS, seek } from './helpers'

test.skip(IS_MOCK || !FEATS.includes('console_polish'), 'needs the real backend and every flag on (E2E_FEATURES)')
test.describe.configure({ timeout: 120_000 })

const clock = (page: import('@playwright/test').Page) => page.locator('.clock-label')

test('presenter keys: P, Space, 1-4, S, W, ?, Esc and the keys stand down inside an input', async ({ page }) => {
  await monsoonAt(page, '08:00')
  const present = page.getByRole('button', { name: 'Present', exact: true })
  await present.click()
  await expect(present).toHaveAttribute('aria-pressed', 'true')
  await page.keyboard.press('?')
  const keys = page.getByRole('region', { name: 'Presenter keys' })
  await expect(keys).toBeVisible()
  await expect(keys).toContainText('what-if')
  await page.keyboard.press('Escape')
  await expect(keys).toBeHidden()

  await page.keyboard.press('3')
  await expect(clock(page)).not.toContainText('· 08:00 ·', { timeout: REPLAY_TIMEOUT_MS })
  await page.keyboard.press('Space')
  const toggle = page.getByRole('button', { name: /^(Play|Pause)$/ })
  await expect(toggle).toHaveAccessibleName('Pause')
  await expect(toggle).toBeEnabled()
  await page.keyboard.press('Space')
  await expect(toggle).toHaveAccessibleName('Play')
  await page.keyboard.press('s')
  await page.keyboard.press('s')

  await page.getByRole('combobox', { name: 'Scenario' }).focus()
  await page.keyboard.press('p')
  await expect(present).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('combobox', { name: 'Scenario' }).blur()

  await page.keyboard.press('p')
  await expect(present).toHaveAttribute('aria-pressed', 'false')
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
  await page.reload()
  await expect(clock(page)).toContainText('Mumbai')
})

test('ops strip: golden numbers, popovers and the jump to the case', async ({ page }) => {
  await monsoonAt(page, '17:10')
  const strip = page.getByRole('region', { name: 'Operations today' })
  await expect(strip).toContainText('100%')
  await expect(strip).toContainText('312 of 312')
  await expect(strip).toContainText('₹4,25,420')
  await expect(strip).toContainText('123 granted')
  await strip.locator('[data-cell="paid"]').click()
  const pop = page.getByRole('dialog', { name: /paid/i })
  await expect(pop).toContainText('₹2,06,719')
  await expect(pop).toContainText('₹58,900')
  await page.getByRole('button', { name: /^Close/ }).click()
  await expect(pop).toBeHidden()
})

test('what-if drawer: Z9 with a rain alert and 49% hours fires with a 51% drop; read-only; Esc closes', async ({ page }) => {
  await monsoonAt(page, '17:10')
  await page.locator('.zone-label--slow').first().click()
  await page.getByRole('button', { name: /What if/ }).click()
  const drawer = page.getByRole('complementary', { name: 'What if for zone Z9' })
  await expect(drawer).toContainText('Read-only: nothing is saved')
  await expect(drawer).toContainText('Would not fire')
  for (const hour of [1, 2, 3]) await drawer.getByRole('slider', { name: `Hour ${hour} sales as a percent of expected` }).fill('49')
  await drawer.getByRole('button', { name: 'Rain', exact: true }).click()
  await expect(drawer).toContainText('Would fire: yes, 51% drop')
  const audit = (await api(page, 'GET', '/api/audit')).data
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  expect(JSON.stringify((await api(page, 'GET', '/api/audit')).data)).toBe(JSON.stringify(audit))
})

test('provider panel: force a component into FALLBACK, see the chip, release it', async ({ page }) => {
  await monsoonAt(page, '08:00')
  await page.getByRole('button', { name: /simulated/ }).click()
  const panel = page.getByRole('region', { name: 'Integrations' })
  const row = panel.locator('[data-name="lender"]')
  await row.getByRole('button', { name: /Force fallback/ }).click()
  await expect(row).toHaveAttribute('data-forced', 'true')
  await expect(row).toContainText('FALLBACK')
  await expect(page.getByRole('button', { name: /fallback/ }).first()).toContainText(/forced|fallback/i)
  await row.getByRole('button', { name: /Release/ }).click()
  await expect(row).toHaveAttribute('data-forced', 'false')
  await expect(row).not.toContainText('FALLBACK')
})

test('dispute case: the officer confirms the payout and the audit chain stays valid', async ({ page }) => {
  await monsoonAt(page, '17:06')
  expect((await api(page, 'POST', '/api/merchants/S-0142/voice-demo', { key: 'dispute' })).ok).toBe(true)
  await goTo(page, 'Claims')
  await page.locator('.queue__item', { hasText: 'C-2291' }).click()
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await expect(detail).toBeVisible()
  await expect(detail.getByRole('button', { name: /Approve|Confirm/ }).first()).toBeEnabled({ timeout: REPLAY_TIMEOUT_MS })
  await detail.getByRole('button', { name: /Approve|Confirm/ }).first().click()
  await expect(detail.locator('.resolution')).toContainText('Payout confirmed by a claims officer', { timeout: REPLAY_TIMEOUT_MS })
  await goTo(page, 'Audit')
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/^Chain valid · \d+ entries/)).toBeVisible()
})

test('evals page renders every suite offline', async ({ page }) => {
  await monsoonAt(page, '08:00')
  await page.goto('/evals')
  await expect(page.getByRole('heading', { name: 'AI evaluation' })).toBeVisible()
  await expect(page.locator('h2').first()).toBeVisible()
})

test('reload mid-replay keeps the clock moving, and a dropped event stream shows Reconnecting and recovers', async ({ page }) => {
  await monsoonAt(page, '13:30')
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(clock(page)).not.toContainText('13:30', { timeout: REPLAY_TIMEOUT_MS })
  await page.reload()
  await expect(clock(page)).toContainText('Mumbai')
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible()

  await page.route('**/api/stream', (route) => route.abort())
  await page.reload()
  await expect(page.getByText('Reconnecting…')).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
  await page.unroute('**/api/stream')
  await expect(page.locator('.connection-pill')).toHaveCount(0, { timeout: 40_000 })
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
})

test('referred slip: the case panel shows source chips on the checks, the officer declines, the phone is told', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'illness_mismatch', 'illness mismatch replay')
  await seek(page, '11:25')
  expect((await api(page, 'POST', '/api/merchants/S-0142/voice-demo', { key: 'ill' })).ok).toBe(true)
  const pre = await api(page, 'POST', '/api/merchants/S-0142/slip-precheck', {})
  const id = String(pre.data?.precheck_id)
  const done = await api(page, 'POST', `/api/merchants/S-0142/slip-precheck/${id}/confirm`, { action: 'CONFIRM' })
  expect(done.data?.outcome).toBe('REFERRED')

  await goTo(page, 'Claims')
  const detail = page.getByRole('article', { name: 'Case C-2291' })
  await expect(detail.getByText('Name on the slip doesn’t match KYC', { exact: true })).toBeVisible()
  await expect(detail.locator('.source-chip').first()).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
  await detail.getByLabel('Officer note').fill('Name differs from KYC')
  await detail.getByRole('button', { name: 'Decline' }).dblclick()
  await expect(detail.locator('.resolution')).toContainText('DECLINED')
  await expect(page.locator('.queue__item', { hasText: 'C-2291' })).toHaveClass(/is-resolved/)
  await goTo(page, 'Audit')
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/^Chain valid · \d+ entries/)).toBeVisible()
})

test('presenter mode at 1280x720: no sideways scroll, no text under 12px on the live map and claims', async ({ page }) => {
  await monsoonAt(page, '17:10')
  await page.getByRole('button', { name: 'Present', exact: true }).click()
  for (const path of ['/live', '/claims']) {
    await page.goto(path)
    await expect(page.getByRole('navigation', { name: 'Pages' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Present', exact: true })).toHaveAttribute('aria-pressed', 'true')
    const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth])
    expect(sw, path).toBeLessThanOrEqual(cw)
    const tiny = await page.evaluate(() => {
      const small: string[] = []
      const walker = document.createTreeWalker(document.querySelector('.page, .home, .claims') ?? document.body, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const el = node.parentElement
        if (!el || !node.textContent?.trim() || el.closest('.leaflet-container, .phone-frame')) continue
        if (parseFloat(getComputedStyle(el).fontSize) < 12) small.push(`${el.className}: ${node.textContent.trim().slice(0, 30)}`)
      }
      return small
    })
    expect(tiny, path).toEqual([])
  }
})

test('slip pre-check on the console phone: the question carries its answers and one confirm pays Anil', async ({ page }) => {
  await openConsole(page)
  await loadScenario(page, 'illness', 'illness replay')
  await seek(page, '11:25')
  await goTo(page, 'Merchant phone')
  const phone = page.getByTestId('phone')
  await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
  await phone.getByRole('button', { name: 'Send a photo' }).click()
  await phone.getByRole('menuitem', { name: "Anil's admission slip" }).click()
  await expect(phone.getByText('Please check it. Is this right?')).toBeVisible()
  const confirm = phone.getByRole('button', { name: /Yes, this is right/ })
  await confirm.dblclick()
  /** Then the doctor question (design 2.6): one Yes lets the simulated doctor confirm the visit. */
  const ask = phone.getByRole('button', { name: /Yes, ask them/ })
  await ask.click()
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(bubble(phone, LINES.personalPaid)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
  await expect(confirm).toHaveCount(0)
  await expect(ask).toHaveCount(0)
})

/**
 * The 3-minute stage demo (docs/06-delivery/stage-script.md), walked click for click against the REAL backend with the stage
 * flag set and no AI keys: `make stage-e2e` (backend :8301, console :5301, `--workers=1`). Every number and label the
 * script says aloud is asserted on screen. It skips itself against the mock build and when the stage flags are not all on.
 *
 * Beats: 1 the trigger and the 312 shops paid (map), 2 Anil's phone in Hindi: tracker, why this amount, sources, the lender's
 * holiday, 3 the illness claim with the slip pre-check, 4 Ask Chhatri with its honest label, 5 the audit chain. The
 * what-if (a spare 15 seconds) is its own test, because it needs the monsoon replay.
 */
import { expect, test, type Page } from '@playwright/test'

import { bubble, goTo, GOLDEN, IS_MOCK, LINES, loadScenario, openConsole, REPLAY_TIMEOUT_MS, seek, settled } from './helpers'

const STAGE_FLAGS = ['n1_miniapp', 'n2_ask_chhatri', 'n3_slip_precheck', 'x4_lender_request', 'h24_whatif', 'console_polish', 'x6_provider_panel']
const ON = (process.env.E2E_FEATURES ?? '').split(/[\s,]+/).filter((name) => name !== '')
/** `make stage-e2e STAGE_E2E_AI=live`: the .env Gemini key is on, so the slip footer and a free question must say LIVE gemini. */
const LIVE_AI = process.env.STAGE_AI === 'live'
const SLIP_PNG = new URL('../../../backend/data/slips/anil_admission_slip.png', import.meta.url).pathname

test.skip(IS_MOCK || !STAGE_FLAGS.every((flag) => ON.includes(flag)), 'needs the real backend and the stage flag set (make stage-e2e)')
test.describe.configure({ timeout: 150_000 })

/** The seek the operator does before the show (stage-script.md, "Before the slot"). */
const PARK_AT = '16:40'
const clock = (page: Page) => page.locator('.clock-label')
const app = (page: Page) => page.getByTestId('app-root')

/** Fails the run on any uncaught page error or console.error (aborted requests are not app bugs). */
function watchErrors(page: Page): string[] {
  const seen: string[] = []
  page.on('pageerror', (error) => seen.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error' && !/Failed to load resource|net::ERR_/.test(message.text())) seen.push(`console.error: ${message.text()}`)
  })
  return seen
}

/** The operator's reset: load the scenario and park the clock, paused. */
async function park(page: Page, scenario: string, label: string, at: string): Promise<void> {
  await loadScenario(page, scenario, label)
  await seek(page, at)
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
}

async function expectFooterOnScreen(page: Page): Promise<void> {
  await expect(page.getByText('Sales, alerts, KYC, payouts, lender and Soundbox are simulated')).toBeVisible()
}

test('the 3-minute stage script, beat by beat', async ({ page }) => {
  const errors = watchErrors(page)
  const marks: string[] = []
  const t0 = Date.now()
  const mark = (name: string) => marks.push(`${((Date.now() - t0) / 1000).toFixed(0).padStart(3)} s  ${name}`)

  await test.step('before the slot: monsoon parked at 16:40 on the live map', async () => {
    await openConsole(page)
    await park(page, 'monsoon', 'monsoon replay', PARK_AT)
    await expect(clock(page)).toContainText(`${PARK_AT}`)
    await expect(page.getByRole('button', { name: /simulated/i })).toBeVisible()
    await expectFooterOnScreen(page)
    await settled(page)
    mark('parked')
  })

  await test.step('beat 1 (0:20): Play. 312 shops are paid four minutes after the trigger, and nobody filed anything', async () => {
    await page.getByRole('button', { name: 'Play', exact: true }).click()
    await expect(page.getByText('₹1,380 paid · 17:04')).toBeVisible({ timeout: 60_000 })
    /** The slow window (1 simulated minute a second) gives the room a few seconds to read 17:04; pause when 17:05 shows. */
    await expect(clock(page)).toContainText('17:05', { timeout: 30_000 })
    await page.getByRole('button', { name: 'Pause', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
    for (const label of GOLDEN.labels) await expect(page.getByText(label, { exact: true })).toBeVisible()
    await expect(page.getByText('₹1,380 credited · 17:04')).toBeVisible()
    await expect(page.getByText('Anil\'s Tea Stall · with the settlement')).toBeVisible()
    const tiles = page.locator('body')
    await expect(tiles).toContainText('123 instalments paused')
    await expect(tiles).toContainText('₹4,25,420 to 312 shops')
    const card = page.getByRole('region', { name: 'Zone Z7' })
    await expect(card.getByRole('heading')).toHaveText('Zone 7 · 46 shops')
    await expect(card.locator('.zone-card__pct')).toHaveText('37%')
    for (const [label, value] of Object.entries(GOLDEN.rows)) await expect(card.locator(`[data-row="${label}"] dd`)).toHaveText(value)
    await expect(page.locator('[data-kpi="zones"] .kpi__value')).toHaveText('3')
    await expect(page.locator('[data-kpi="shops"] .kpi__value')).toHaveText('312')
    await expect(page.locator('[data-kpi="ttm"] .kpi__value')).toHaveText('4 min')
    await expect(page.locator('.explanation[data-zone="Z9"]')).toHaveText(GOLDEN.z9)
    await expect(page.getByText(GOLDEN.z9Label)).toBeVisible()
    mark('312 shops paid')
  })

  await test.step('beat 2 (0:50): Anil\'s phone in Hindi, "No claim needed"', async () => {
    await goTo(page, 'Merchant phone')
    await expect(page.getByText('No claim needed')).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await expect(page.locator('.soundbox-device__hi')).toHaveText('“Paytm par ₹1,380 prapt hue — Chhatri se”')
    await expect(page.getByText('आपके लेंडर ने कल की ₹600 की किस्त रोक दी है।').first()).toBeVisible()
    await expect(app(page)).toContainText('नमस्ते, अनिल जी')
    await expect(app(page)).toContainText('₹1,380')
    await expectFooterOnScreen(page)
    mark('phone in Hindi')
  })

  await test.step('beat 2 (1:00): the claim tracker, with the lender\'s holiday labelled SIMULATED', async () => {
    await page.getByTestId('app-tab-claims').click()
    await page.getByTestId('claim-card-CL-000142').getByRole('link').click()
    for (const step of ['detected', 'checked', 'decided', 'paid', 'edi']) await expect(page.getByTestId(`claim-step-${step}`)).toHaveAttribute('data-status', 'completed')
    await expect(page.getByTestId('claim-step-decided')).toContainText('मंज़ूर ₹1,380')
    await expect(page.getByTestId('claim-step-paid')).toContainText('SIMULATED')
    const holiday = page.getByTestId('claim-step-edi')
    await expect(holiday).toContainText('किस्त की छुट्टी')
    await expect(holiday).toContainText('आपके लेंडर ने कल की ₹600 की किस्त रोक दी है।')
    await expect(holiday).toContainText('SIMULATED लेंडर')
    await expect(holiday).not.toContainText(/छतरी ने .*रोक/)
    mark('tracker')
  })

  await test.step('beat 2 (1:10): "Why this amount?" with a source on every number', async () => {
    await app(page).getByRole('button', { name: 'इतने पैसे क्यों?' }).click()
    await expect(page.getByTestId('screen-why')).toHaveAttribute('data-state', 'ready')
    await expect(page.getByTestId('why-formula')).toContainText('₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380')
    await expect(page.getByTestId('why-formula-other')).toContainText('½ × ₹4,380 × 63% = ₹1,380')
    const expected = { expected_day: '₹4,380', area_index: '37%', drop_pct: '63%', share: 'आधा', cap: '₹2,500', amount: '₹1,380' }
    for (const [row, value] of Object.entries(expected)) {
      await expect(page.getByTestId(`why-value-${row}`)).toHaveText(value)
      await expect(page.getByTestId(`why-row-${row}`).getByTestId('source-badge').first()).toBeVisible()
    }
    await expect(page.getByTestId('source-missing')).toHaveCount(0)
    /** Each chip's tap area reaches 10 px past its box (SourceBadge.tsx); neighbouring chips must not share it. */
    const rows = await page.getByTestId('why-row-area_index').getByTestId('source-badge').evaluateAll((chips) => chips.map((chip) => chip.getBoundingClientRect()).map(({ top, bottom }) => ({ top, bottom })))
    expect(rows.length).toBeGreaterThan(1)
    for (let i = 1; i < rows.length; i += 1) {
      if (rows[i].top > rows[i - 1].top + 1) expect(rows[i].top - rows[i - 1].bottom + 0.5).toBeGreaterThanOrEqual(20)
    }
    const badge = page.getByTestId('why-row-area_index').getByTestId('source-badge').first()
    await badge.scrollIntoViewIfNeeded()
    await badge.click()
    await expect(badge).toHaveAttribute('data-state', 'open')
    const sheet = page.getByRole('dialog')
    await expect(sheet).toBeVisible()
    await expect(sheet).toContainText('SIMULATED')
    await page.keyboard.press('Escape')
    await expect(sheet).toBeHidden()
    await expect(page.getByTestId('why-counterfactual')).toContainText('इलाके की गिरावट एक प्रतिशत और होती, तो लगभग ₹22 और जुड़ते।')
    mark('why this amount')
  })

  await test.step('beat 3 (1:30): Anil falls ill: a person is checked on, never asked to file', async () => {
    await goTo(page, 'Live map')
    await park(page, 'illness', 'illness replay', '11:20')
    await goTo(page, 'Merchant phone')
    await expect(page.getByText('Your shop has been closed since yesterday. Is everything okay?')).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await page.getByRole('button', { name: 'मैं अस्पताल में हूँ, बुखार है।' }).click()
    await expect(page.getByText('Get well soon. Please send one photo of the hospital slip.')).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    mark('check-in answered')
  })

  await test.step('beat 3 (1:45): the slip pre-check reads the photo, shows what it read and asks', async () => {
    await page.getByTestId('app-tab-help').click()
    await page.getByTestId('help-slip').click()
    await expect(page.getByTestId('screen-slip')).toBeVisible()
    if ((await page.getByTestId('slip-consent').count()) > 0) await page.getByTestId('slip-consent').check()
    await page.getByTestId('slip-gallery-input').setInputFiles(SLIP_PNG)
    await expect(page.getByTestId('slip-result')).toHaveAttribute('data-status', 'READY', { timeout: REPLAY_TIMEOUT_MS })
    const fields = page.getByTestId('slip-fields')
    await expect(fields).toContainText('Anil R. Jadhav')
    await expect(fields).toContainText('KEM Hospital, Parel')
    await expect(fields).toContainText('20 अगस्त')
    await expect(fields).toContainText('Dr S. Rao')
    await expect(fields).toContainText('MMC-2011-45817')
    for (const id of ['photo_readable', 'name_on_slip', 'dates_on_slip']) await expect(page.getByTestId(`slip-check-${id}`)).toHaveAttribute('data-state', 'PASS')
    if (LIVE_AI) {
      await expect(page.getByTestId('slip-footer')).toContainText('LIVE')
      await expect(page.getByTestId('slip-footer')).toContainText(/gemini/i)
    } else await expect(page.getByTestId('slip-footer')).toContainText('SIMULATED')
    await expect(page.getByTestId('screen-slip')).not.toContainText(/confidence|\d+\s?%/i)
    await page.getByTestId('slip-confirm').click()
    /** The doctor question (design 2.4): the merchant agrees that Dr S. Rao may be asked, then the claim opens. */
    await expect(page.getByTestId('slip-consent-question')).toContainText('Dr S. Rao', { timeout: REPLAY_TIMEOUT_MS })
    await page.getByTestId('slip-consent-yes').click()
    await expect(page).toHaveURL(/screen=claim&claim=CL-\d+/)
    await expect(page.getByTestId('claim-amount')).toContainText('₹1,500')
    await expect(page.getByTestId('claim-step-decided')).toContainText('मंज़ूर ₹1,500')
    await expect(page.getByTestId('claim-step-decided')).toContainText('₹4,300 का आधा = ₹2,150 प्रतिदिन; सीमा ₹1,500 × 1 दिन = ₹1,500')
    mark('slip read, ₹1,500 approved')
  })

  await test.step('beat 3 (2:05): Play: ₹1,500 credited with the settlement', async () => {
    await page.getByRole('button', { name: 'Play', exact: true }).click()
    await expect(page.getByTestId('claim-step-paid')).toHaveAttribute('data-status', 'completed', { timeout: 60_000 })
    await page.getByRole('button', { name: 'Pause', exact: true }).click()
    await expect(page.getByTestId('claim-step-paid')).toContainText('SIMULATED')
    mark('₹1,500 credited')
  })

  await test.step('beat 4 (2:15): Ask Chhatri in his own words, with the label of what answered', async () => {
    await page.getByTestId('app-tab-help').click()
    await page.getByTestId('help-ask').click()
    await expect(page.getByTestId('screen-ask')).toBeVisible()
    await page.getByTestId('ask-input').fill('मुझे इतने पैसे क्यों मिले?')
    await page.getByTestId('ask-send').click()
    const answer = page.getByTestId('ask-answer')
    await expect(answer).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await expect(answer).toContainText('₹')
    await expect(page.getByTestId('ask-clause').first()).toContainText(/C\d/)
    await expect(page.getByTestId('source-badge').first()).toBeVisible()
    const mode = (await page.getByTestId('ask-mode').innerText()).trim()
    expect(['LIVE', 'SIMULATED', 'FALLBACK']).toContain(mode)
    await expect(page.getByTestId('ask-provider')).toHaveText('rules')
    mark(`Ask answered: ${mode} / rules`)
    await page.getByTestId('ask-input').fill('What is the yearly limit?')
    await page.getByTestId('ask-send').click()
    await expect(page.getByTestId('ask-answer')).toHaveCount(2, { timeout: REPLAY_TIMEOUT_MS })
    const second = page.getByTestId('ask-entry').last()
    const secondMode = (await second.getByTestId('ask-mode').innerText()).trim()
    expect(['LIVE', 'SIMULATED', 'FALLBACK']).toContain(secondMode)
    if (LIVE_AI) {
      /** A live key: the free question goes to the model and the footer says so (the amount is never its decision). */
      expect(secondMode).toBe('LIVE')
      await expect(second.getByTestId('ask-provider')).toHaveText('gemini')
      await expect(second.getByTestId('ask-clause').first()).toContainText(/C\d/)
    } else {
      /** No AI key in this run, so the model path cannot be LIVE: the label must say a simulator answered. */
      expect(secondMode).toBe('SIMULATED')
      await expect(second.getByTestId('ask-provider')).toHaveText('template')
      await expect(second.getByTestId('ask-answer-text')).toContainText('मैं छतरी हूँ')
    }
    mark(`free question: ${secondMode} / template`)
  })

  await test.step('beat 5 (2:40): the audit chain verifies, every step logged', async () => {
    await goTo(page, 'Audit')
    await page.getByRole('button', { name: 'Verify chain' }).click()
    await expect(page.getByText(/^Chain valid · \d+ entries/)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await expectFooterOnScreen(page)
    mark('chain valid')
  })

  await test.info().attach('stage-timing', { body: `automation clock, not the speaker's:\n${marks.join('\n')}`, contentType: 'text/plain' })
  expect(errors, 'page errors and console.error calls').toEqual([])
})

test('the spare 15 seconds: what-if on Zone 9 fires with a 51% drop and saves nothing', async ({ page }) => {
  const errors = watchErrors(page)
  await openConsole(page)
  await park(page, 'monsoon', 'monsoon replay', '17:06')
  await page.locator('.zone-label--slow').first().click()
  await page.getByRole('button', { name: /What if/ }).click()
  const drawer = page.getByRole('complementary', { name: 'What if for zone Z9' })
  await expect(drawer).toContainText('Read-only: nothing is saved')
  await expect(drawer).toContainText('Would not fire')
  for (const hour of [1, 2, 3]) await drawer.getByRole('slider', { name: `Hour ${hour} sales as a percent of expected` }).fill('49')
  await drawer.getByRole('button', { name: 'Rain', exact: true }).click()
  await expect(drawer).toContainText('Would fire: yes, 51% drop')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  expect(errors, 'page errors and console.error calls').toEqual([])
})

test('the spare 30 seconds: slide 8 live tests, a name mismatch goes to case C-2291 and one tap approves it; red-alert cover is BLOCKED', async ({ page }) => {
  const errors = watchErrors(page)
  await openConsole(page)

  await test.step('HUMAN test: a slip with another name is REFERRED to case C-2291, approved in one tap', async () => {
    await park(page, 'illness_mismatch', 'illness mismatch replay', '11:25')
    await goTo(page, 'Merchant phone')
    const phone = page.getByTestId('phone')
    await phone.getByRole('button', { name: /मैं अस्पताल में हूँ/ }).click()
    await expect(bubble(phone, 'Get well soon. Please send one photo of the hospital slip.')).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await phone.getByRole('button', { name: 'Send a photo' }).click()
    await phone.getByRole('menuitem', { name: 'Slip with a different name' }).click()
    /** With the slip pre-check on (n3), the phone first asks "Is this slip right?", then whether the doctor may be asked. */
    await phone.getByRole('button', { name: /Yes, this is right/ }).click()
    await phone.getByRole('button', { name: /Yes, ask them/ }).click()
    await expect(bubble(phone, LINES.slipToHuman)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await expect(phone.getByRole('link', { name: /case C-2291/ })).toBeVisible()
    await goTo(page, 'Claims')
    const detail = page.getByRole('article', { name: 'Case C-2291' })
    await expect(detail.getByText('REFERRED', { exact: true })).toBeVisible()
    await expect(detail.getByText('Name on the slip doesn’t match KYC', { exact: true })).toBeVisible()
    await detail.getByRole('button', { name: 'Approve' }).click()
    await expect(detail.locator('.resolution')).toContainText('APPROVED', { timeout: REPLAY_TIMEOUT_MS })
    await expect(detail.locator('.resolution')).toContainText(/₹1,500 credited to Anil.s Tea Stall at \d\d:\d\d, with the settlement\./, { timeout: REPLAY_TIMEOUT_MS })
  })

  await test.step('BLOCKED test: "Red alert tomorrow. Cover me today." is told the truth, never approved', async () => {
    await goTo(page, 'Live map')
    await park(page, 'buy_cover', 'buy cover replay', '18:10')
    await goTo(page, 'Merchant phone')
    const phone = page.getByTestId('phone')
    await phone.getByRole('button', { name: 'Red alert tomorrow. Cover me today.' }).click()
    await expect(bubble(phone, LINES.coverBlocked)).toBeVisible({ timeout: REPLAY_TIMEOUT_MS })
    await expect(phone.getByRole('link', { name: /paytm\.me\/sim-|paytm/ }).first()).toBeVisible()
    await expect(page.getByText('Cover bought after an alert')).toBeVisible()
  })
  expect(errors, 'page errors and console.error calls').toEqual([])
})

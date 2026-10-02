/** S6 Why this amount (fs-04 8, H2, H13, H14): the formula, each number with its sources, and what would have changed it (AC-26, AC-40). */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { Receipt } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { referredSession, session, stubReceipt } from '../../test/claimScenes'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

const text = (id: string) => screen.getByTestId(id).textContent ?? ''

async function openWhy(kit: { backend: MockBackend }, decision = 'D-000142', search = 'lang=en', state = 'ready') {
  backend = kit.backend
  const view = renderStandalone(`/merchant/S-0142/app?${search}&screen=why&decision=${decision}`, kit.backend)
  await waitFor(() => expect(screen.getByTestId('screen-why').getAttribute('data-state')).toBe(state))
  return view
}

async function anilReceipt(): Promise<Receipt> {
  const kit = await session('monsoon', '17:05')
  const receipt = await kit.api.receipt('D-000142')
  kit.backend.dispose()
  return receipt
}

describe("Anil's decision (AC-26)", () => {
  it('shows the formula in English, large, and the Hindi formula small under it, each in its own language', async () => {
    await openWhy(await session('monsoon', '17:05'))
    expect(text('why-formula')).toBe('½ × ₹4,380 × 63% = ₹1,380')
    expect(screen.getByTestId('why-formula').getAttribute('lang')).toBeNull()
    expect(text('why-formula-other')).toBe('₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380')
    expect(screen.getByTestId('why-formula-other').getAttribute('lang')).toBe('hi')
  })

  it('shows the Hindi formula large in Hindi and the English one small', async () => {
    await openWhy(await session('monsoon', '17:05'), 'D-000142', 'x=1')
    expect(text('why-formula')).toBe('₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380')
    expect(text('why-formula-other')).toBe('½ × ₹4,380 × 63% = ₹1,380')
    expect(screen.getByTestId('why-formula-other').getAttribute('lang')).toBe('en')
  })

  it('lists the numbers with their values, and every row carries a source badge', async () => {
    await openWhy(await session('monsoon', '17:05'))
    const rows = within(screen.getByTestId('why-numbers')).getAllByTestId(/^why-row-/)
    expect(rows.map((row) => row.getAttribute('data-testid'))).toEqual(['why-row-expected_day', 'why-row-area_index', 'why-row-drop_pct', 'why-row-share', 'why-row-cap', 'why-row-amount'])
    expect(['expected_day', 'area_index', 'drop_pct', 'share', 'cap', 'amount'].map((key) => text(`why-value-${key}`))).toEqual(['₹4,380', '37%', '63%', 'Half', '₹2,500', '₹1,380'])
    for (const row of rows) {
      const badges = within(row).getByTestId('why-badges')
      expect(within(badges).getAllByTestId('source-badge').length).toBeGreaterThan(0)
    }
    expect(screen.queryByTestId('source-missing')).toBeNull()
  })

  it('labels the rows in plain words and explains four of them through the jargon lens', async () => {
    await openWhy(await session('monsoon', '17:05'))
    expect(text('why-row-expected_day')).toContain('Your usual day')
    expect(text('why-row-drop_pct')).toContain('Area drop')
    expect(text('why-row-share')).toContain("Chhatri's share")
    expect(text('why-row-cap')).toContain('Daily limit')
    expect(text('why-row-amount')).toContain('Your payout')
    for (const term of ['expected_day', 'area_drop', 'payout_share', 'daily_cap']) expect(screen.getByTestId(`term-${term}`).getAttribute('aria-haspopup')).toBe('dialog')
  })

  it('gives each source badge its own mode: the sales index is SIMULATED, the payout rules are a fixed setting', async () => {
    await openWhy(await session('monsoon', '17:05'))
    const forecast = within(screen.getByTestId('why-row-expected_day')).getByTestId('source-badge')
    expect(forecast.getAttribute('data-origin')).toBe('SIMULATED')
    expect(forecast.textContent).toContain('SIMULATED')
    const share = within(screen.getByTestId('why-row-share')).getByTestId('source-badge')
    expect(share.getAttribute('data-origin')).toBe('CONFIG')
    expect(share.textContent).not.toMatch(/SIMULATED|LIVE/)
    expect(share.textContent).toContain('pilot-0.1')
  })

  it('opens the sheet of a badge with the record, its time and its type', async () => {
    await openWhy(await session('monsoon', '17:05'))
    fireEvent.click(within(screen.getByTestId('why-row-expected_day')).getByTestId('source-badge'))
    const sheet = await screen.findByTestId('source-sheet')
    expect(sheet.textContent).toContain('forecast:S-0142:2025-08-19')
    expect(text('source-sheet-origin')).toBe('SIMULATED')
  })

  it('shows the counterfactual sentences exactly as the receipt sends them, with the footer under them', async () => {
    const receipt = await anilReceipt()
    await openWhy(await session('monsoon', '17:05'))
    const shown = Array.from(screen.getByTestId('why-counterfactual').children).map((node) => node.textContent)
    expect(shown).toEqual(receipt.counterfactuals.map((item) => item.text_en))
    expect(shown.length).toBeGreaterThan(0)
    expect(screen.getByTestId('why-counterfactual').parentElement?.textContent).toContain('This explains this one decision.')
  })

  it('shows the counterfactual in Hindi in Hindi, as received', async () => {
    const receipt = await anilReceipt()
    await openWhy(await session('monsoon', '17:05'), 'D-000142', 'x=1')
    const shown = Array.from(screen.getByTestId('why-counterfactual').children).map((node) => node.textContent)
    expect(shown).toEqual(receipt.counterfactuals.map((item) => item.text_hi))
  })

  it('has no heading above the app bar title and a heading for each block', async () => {
    await openWhy(await session('monsoon', '17:05'))
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getAllByRole('heading', { level: 2 }).map((node) => node.textContent)).toContain('Your numbers')
  })
})

describe('what this screen leads to', () => {
  it('says see_receipt next, and the bar opens the receipt of this decision', async () => {
    await openWhy(await session('monsoon', '17:05'))
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_receipt')
    fireEvent.click(screen.getByTestId('app-nba-action'))
    await screen.findByTestId('screen-receipt')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142')
  })

  it('takes "This is wrong" to the claim and puts the focus on its dispute button', async () => {
    await openWhy(await session('monsoon', '17:05'))
    fireEvent.click(screen.getByTestId('why-dispute'))
    await screen.findByTestId('screen-claim')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142')
    const button = await screen.findByTestId('claim-dispute-button')
    await waitFor(() => expect(document.activeElement).toBe(button))
  })
})

describe('a decision with no amount', () => {
  it('says a person is checking, names the failing check in plain words and still shows the counterfactual', async () => {
    const kit = await referredSession()
    const { items } = await kit.api.claims('S-0142')
    await openWhy(kit, items[0].decision_id ?? '')
    expect(screen.queryByTestId('why-formula')).toBeNull()
    expect(screen.queryByTestId('why-numbers')).toBeNull()
    const card = screen.getByTestId('why-no-amount')
    expect(card.textContent).toContain('Why a person is checking')
    expect(card.textContent).toContain('No amount yet. A person is checking your claim.')
    expect(text('why-reasons')).toContain('The name on the slip does not match your KYC.')
    expect(screen.getByTestId('why-counterfactual')).toBeTruthy()
    expect(screen.queryByTestId('why-dispute')).toBeNull()
  })

  it('gives the built reason of the failing HARD check for a declined decision', async () => {
    const receipt = await anilReceipt()
    const declined: Receipt = {
      ...receipt,
      decision: { ...receipt.decision, outcome: 'DECLINED', amount_paise: 0, amount_label: '₹0' },
      checks: receipt.checks.map((check) => (check.code === 'BELOW_FLOOR' ? { ...check, status: 'FAIL' as const } : check)),
    }
    stubReceipt(declined)
    await openWhy(await session('monsoon', '17:05'))
    expect(text('why-no-amount')).toContain('Not paid')
    expect(text('why-reasons')).toContain("Your area's sales didn't fall below the payout level.")
    expect(screen.queryByTestId('why-formula')).toBeNull()
  })

  it("names a person's decision when an officer declined and no check failed", async () => {
    const receipt = await anilReceipt()
    stubReceipt({ ...receipt, decision: { ...receipt.decision, outcome: 'DECLINED', amount_paise: 0, amount_label: '₹0', decided_by: 'officer:officer' } })
    await openWhy(await session('monsoon', '17:05'))
    expect(text('why-reasons')).toContain("After checking the slip, this claim can't be paid.")
  })
})

describe('when the decision is not there or does not load (AC-40)', () => {
  it('says it could not find an unknown decision and links back to the claims', async () => {
    await openWhy(await session('monsoon', '17:05'), 'D-999999', 'lang=en', 'error')
    expect(text('app-error')).toContain('We could not find this.')
    expect(within(screen.getByTestId('app-error')).getByRole('link').getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=claims')
  })

  it('treats a link with no decision id as not found without asking the API', async () => {
    const get = vi.spyOn(ApiClient.prototype, 'get')
    const kit = await session('monsoon', '17:05')
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=why', kit.backend)
    await waitFor(() => expect(screen.getByTestId('screen-why').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('We could not find this.')
    expect(get.mock.calls.some(([path]) => String(path).includes('/receipt'))).toBe(false)
  })

  it('shows the generic error with its code, and Retry asks again', async () => {
    const real = ApiClient.prototype.get
    let failing = true
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/receipt') && failing) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    await openWhy(await session('monsoon', '17:05'), 'D-000142', 'lang=en', 'error')
    expect(text('app-error')).toContain('Error code: internal_error')
    failing = false
    fireEvent.click(screen.getByTestId('app-error-retry'))
    await waitFor(() => expect(screen.getByTestId('screen-why').getAttribute('data-state')).toBe('ready'))
  })

  it('shows contract_violation when a number arrives with no source', async () => {
    const receipt = await anilReceipt()
    const facts = receipt.explanation.facts.map((fact, index) => (index === 0 ? { ...fact, sources: [] } : fact))
    stubReceipt({ ...receipt, explanation: { ...receipt.explanation, facts } })
    await openWhy(await session('monsoon', '17:05'), 'D-000142', 'lang=en', 'error')
    expect(text('app-error')).toContain('Error code: contract_violation')
    expect(screen.queryByTestId('why-numbers')).toBeNull()
  })

  it('keeps the explanation under the offline banner', async () => {
    await openWhy(await session('monsoon', '17:05'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-why').getAttribute('data-state')).toBe('offline'))
    expect(text('app-offline-banner')).toMatch(/^Offline\. Showing data from/)
    expect(text('why-formula')).toBe('½ × ₹4,380 × 63% = ₹1,380')
  })

  it('draws a formula bar and three rows while loading', async () => {
    const kit = await session('monsoon', '17:05')
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=why&decision=D-000142', kit.backend)
    const root = screen.getByTestId('screen-why')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    await waitFor(() => expect(root.getAttribute('data-state')).toBe('ready'))
  })
})

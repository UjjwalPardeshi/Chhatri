/** S7 Trust receipt (fs-04 8, 10, H3, H13, H14): contents, sources, checks, the counterfactual, print and the log (AC-20, AC-27 to AC-31, AC-40). */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { Receipt as ReceiptBody } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { hi } from '../copy/hi'
import { referredSession, session, stubReceipt } from '../../test/claimScenes'
import { MiniappProvider } from '../shell/MiniappContext'
import { renderStandalone } from '../shell/shellKit'
import { ReceiptContent } from './ReceiptContent'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const text = (id: string) => screen.getByTestId(id).textContent ?? ''

async function openReceipt(kit: { backend: MockBackend }, decision = 'D-000142', search = 'lang=en', state = 'ready') {
  backend = kit.backend
  const view = renderStandalone(`/merchant/S-0142/app?${search}&screen=receipt&decision=${decision}`, kit.backend)
  await waitFor(() => expect(screen.getByTestId('screen-receipt').getAttribute('data-state')).toBe(state))
  return view
}

async function anilReceipt(): Promise<ReceiptBody> {
  const kit = await session('monsoon', '17:05')
  const receipt = await kit.api.receipt('D-000142')
  kit.backend.dispose()
  return receipt
}

const edi = (over: Partial<NonNullable<ReceiptBody['edi']>>): NonNullable<ReceiptBody['edi']> => ({
  request_id: 'EDI-1',
  status: 'GRANTED',
  reason_code: null,
  instalment_date: '2025-08-20',
  instalment_label: '₹600',
  decided_at: '2025-08-19T17:05:00+05:30',
  lender: 'Demo Lender',
  ...over,
})

/** happy-dom has no `window.print`: a stub that counts the calls. */
function stubPrint() {
  const print = vi.fn<() => void>()
  vi.stubGlobal('print', print)
  return print
}

/** The document on its own, in the provider it needs, for a receipt that the parser would never let through. */
function renderContent(receipt: ReceiptBody) {
  const kit = testApi()
  backend = kit.backend
  return render(
    <MemoryRouter initialEntries={['/merchant/S-0142/app?lang=en']}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">
          <ReceiptContent receipt={receipt} />
        </MiniappProvider>
      </LiveProvider>
    </MemoryRouter>,
  )
}

describe("Anil's receipt (AC-27)", () => {
  it('has the decision id, the rules version, the formula, the sources, the audit prefix, the counterfactual and the ladder', async () => {
    const receipt = await anilReceipt()
    await openReceipt(await session('monsoon', '17:05'))
    expect(text('receipt-decision-id')).toBe('D-000142')
    expect(text('receipt-outcome')).toBe('Approved ₹1,380')
    expect(screen.getByTestId('receipt-outcome').getAttribute('data-outcome')).toBe('APPROVED')
    expect(text('receipt-rules-version')).toBe('pilot-0.1')
    expect(text('receipt-formula')).toBe('½ × ₹4,380 × 63% = ₹1,380')
    expect(text('receipt-audit-prefix')).toBe(receipt.audit.hash_short)
    expect(text('receipt-audit-prefix')).toHaveLength(12)
    const badges = within(screen.getByTestId('receipt-sources')).getAllByTestId('source-badge')
    expect(badges.length).toBeGreaterThan(0)
    expect(badges[0].textContent).toContain('SIMULATED')
    expect(badges[0].getAttribute('data-kind')).toBe('FORECAST')
    expect(Array.from(screen.getByTestId('receipt-counterfactual').children).map((node) => node.textContent)).toEqual(receipt.counterfactuals.map((item) => item.text_en))
    const ladder = screen.getByTestId('receipt-grievance-path')
    expect(within(ladder).getAllByRole('listitem')).toHaveLength(4)
    expect(ladder.textContent).toContain('Our claims officer')
    expect(ladder.textContent).toContain('We reply within 24 hours.')
    expect(ladder.textContent).toContain("The insurer's grievance officer")
    expect(ladder.textContent).toContain('IRDAI Bima Bharosa portal')
    expect(ladder.textContent).toContain('Insurance Ombudsman')
  })

  it('opens the sheet of a source badge with the record, its time, its type and the clause', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    fireEvent.click(within(screen.getByTestId('receipt-source-share')).getByTestId('source-badge'))
    const sheet = await screen.findByTestId('source-sheet')
    expect(sheet.textContent).toContain('rules:pilot-0.1:payout_share')
    expect(sheet.textContent).toContain('C4')
    expect(text('source-sheet-origin')).toBe('CONFIG')
  })

  it('says it is a SIMULATED receipt, shows the credit with the payout rail, and no pending note', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    expect(text('receipt-simulated')).toBe('SIMULATED receipt. The data and the payout are not real.')
    expect(text('receipt-payout')).toContain('19 August, 17:04')
    expect(text('receipt-payout')).toContain('SIMULATED payment')
    expect(screen.queryByTestId('receipt-pending-note')).toBeNull()
    expect(text('receipt-heading')).toBe('Your payout receipt')
    expect(text('receipt-decision')).toContain('Decision')
  })

  it('names the clauses it used and who decided', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    const clauses = within(screen.getByTestId('receipt-clauses')).getAllByRole('listitem').map((node) => node.textContent)
    expect(clauses[0]).toContain('C2')
    expect(clauses.join(' ')).toContain('C4')
    expect(clauses.join(' ')).toContain('How much we pay')
    expect(text('receipt-document')).toContain('An automatic rules check (code, not AI)')
  })

  it('has the footer, a print button and no heading above the app bar title', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    expect(text('receipt-footer')).toBe('This receipt explains one decision. It is not a policy document.')
    expect(text('receipt-print')).toBe('Print or save as PDF')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('reads in Hindi by default, with the formula and the labels in Hindi', async () => {
    await openReceipt(await session('monsoon', '17:05'), 'D-000142', 'x=1')
    expect(text('receipt-formula')).toBe('₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380')
    expect(text('receipt-simulated')).toContain('SIMULATED')
    expect(text('receipt-print')).toBe(hi['receipt.btn.print'])
    expect(screen.getByTestId('receipt-grievance-path').textContent).toContain(hi['grv.step.PAYTM_DISPUTE'])
  })
})

describe('who authorised this money', () => {
  it('leads the document: the policy engine, the rules version, no authority for AI, and "Verify this decision"', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    const block = screen.getByTestId('receipt-authority')
    expect(screen.getByTestId('receipt-document').contains(block)).toBe(true)
    expect(block.compareDocumentPosition(screen.getByTestId('receipt-decision')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(block.getAttribute('data-decided-by')).toBe('engine')
    expect(text('receipt-authority-title')).toBe('Who authorised this money')
    expect(text('receipt-decided-by')).toContain('The policy engine')
    expect(text('receipt-decided-by')).toContain('An automatic rules check (code, not AI)')
    expect(within(block).getByTestId('receipt-rules-version').textContent).toBe('pilot-0.1')
    expect(screen.getAllByTestId('receipt-rules-version')).toHaveLength(1)
    expect(text('receipt-ai-authority')).toContain('AI authority')
    expect(text('receipt-ai-authority')).toContain('None. AI can explain this decision, but it cannot decide or change a payout.')
    expect(within(block).getByTestId('receipt-verify').textContent).toContain('Verify this decision')
    expect(within(block).getByTestId('receipt-check-log').textContent).toBe('Check the log')
    expect(screen.getByTestId('receipt-verify').className).toContain('print:hidden')
  })

  it('names a claims officer when an officer decided, under the rules version of that decision, and still gives AI none', async () => {
    const kit = await referredSession()
    await kit.api.approve('C-2291', '')
    kit.backend.step(5)
    const { items } = await kit.api.claims('S-0142')
    const receipt = await kit.api.receipt(items[0].decision_id ?? '')
    await openReceipt(kit, receipt.decision.id)
    const block = screen.getByTestId('receipt-authority')
    expect(block.getAttribute('data-decided-by')).toBe('officer')
    expect(text('receipt-authority-title')).toBe('Who authorised this money')
    expect(text('receipt-decided-by')).toContain('A claims officer')
    expect(text('receipt-decided-by')).not.toContain('The policy engine')
    expect(within(block).getByTestId('receipt-rules-version').textContent).toBe(receipt.decision.rules_version)
    expect(text('receipt-ai-authority')).toContain('None. AI can explain this decision')
  })

  it('asks "Who decided this" on a record with no money yet, and the engine decided it', async () => {
    const kit = await referredSession()
    const { items } = await kit.api.claims('S-0142')
    await openReceipt(kit, items[0].decision_id ?? '')
    expect(text('receipt-authority-title')).toBe('Who decided this')
    expect(screen.getByTestId('receipt-authority').getAttribute('data-decided-by')).toBe('engine')
    expect(text('receipt-decided-by')).toContain('The policy engine')
  })

  it('speaks Hindi by default and keeps the rules version as the receipt wrote it', async () => {
    await openReceipt(await session('monsoon', '17:05'), 'D-000142', 'x=1')
    expect(text('receipt-authority-title')).toBe(hi['receipt.authority.title'])
    expect(text('receipt-decided-by')).toContain(hi['receipt.authority.engine'])
    expect(text('receipt-ai-authority')).toContain(hi['receipt.authority.ai'])
    expect(text('receipt-verify')).toContain(hi['receipt.authority.verify'])
    expect(text('receipt-rules-version')).toBe('pilot-0.1')
  })
})

describe('the checks', () => {
  it('collapse under one sentence when all passed, and open with every check, its words and its sources', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    const box = screen.getByTestId('receipt-checks')
    expect(box.getAttribute('data-open')).toBe('false')
    expect(box.textContent).toContain('All 9 checks passed.')
    const toggle = screen.getByTestId('receipt-checks-toggle')
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(toggle)
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(box.getAttribute('data-open')).toBe('true')
    const row = screen.getByTestId('receipt-check-BELOW_FLOOR')
    expect(row.getAttribute('data-status')).toBe('PASS')
    expect(row.getAttribute('data-severity')).toBe('HARD')
    expect(row.textContent).toContain("Your area's sales stayed below the payout level")
    expect(row.textContent).toContain('Passed')
    expect(row.textContent).toContain('What we found')
    expect(row.textContent).toContain('What is needed')
    expect(within(row).getAllByTestId('source-badge').length).toBeGreaterThan(0)
  })

  it('stay open when a check needs a look, and the receipt is a record while no payout is credited', async () => {
    const kit = await referredSession()
    const { items } = await kit.api.claims('S-0142')
    await openReceipt(kit, items[0].decision_id ?? '')
    expect(screen.getByTestId('receipt-checks').getAttribute('data-open')).toBe('true')
    expect(screen.getByTestId('receipt-checks-toggle').getAttribute('aria-expanded')).toBe('true')
    expect(text('receipt-heading')).toBe('Your decision record')
    expect(text('receipt-pending-note')).toBe('No receipt yet. A receipt appears after a payout is credited.')
    expect(screen.queryByTestId('receipt-formula')).toBeNull()
    expect(screen.queryByTestId('receipt-sources')).toBeNull()
    expect(screen.queryByTestId('receipt-payout')).toBeNull()
    expect(text('receipt-outcome')).toBe('With a claims officer')
    expect(screen.getByTestId('receipt-outcome').getAttribute('data-outcome')).toBe('REFERRED')
    const name = screen.getByTestId('receipt-check-NAME_MATCHES_KYC')
    expect(name.getAttribute('data-severity')).toBe('SOFT')
    expect(['FAIL', 'UNSURE']).toContain(name.getAttribute('data-status'))
  })

  it('show WAIVED_BY_OFFICER on the soft check an officer cleared, and who decided (AC-20)', async () => {
    const kit = await referredSession()
    await kit.api.approve('C-2291', '')
    kit.backend.step(5)
    const { items } = await kit.api.claims('S-0142')
    await openReceipt(kit, items[0].decision_id ?? '')
    expect(screen.getByTestId('receipt-check-NAME_MATCHES_KYC').getAttribute('data-status')).toBe('WAIVED_BY_OFFICER')
    expect(text('receipt-check-NAME_MATCHES_KYC')).toContain('Cleared by a claims officer')
    expect(text('receipt-outcome')).toBe('Approved by a claims officer')
    expect(text('receipt-amount')).toBe('₹1,500')
    expect(text('receipt-document')).toContain('A claims officer')
    expect(screen.getByTestId('receipt-checks').getAttribute('data-open')).toBe('true')
  })
})

describe('the counterfactual (AC-29)', () => {
  it('is the text of the mismatch decision exactly as the API sent it', async () => {
    const kit = await referredSession()
    const { items } = await kit.api.claims('S-0142')
    const receipt = await kit.api.receipt(items[0].decision_id ?? '')
    await openReceipt(kit, items[0].decision_id ?? '')
    const shown = Array.from(screen.getByTestId('receipt-counterfactual').children).map((node) => node.textContent)
    expect(shown).toEqual(receipt.counterfactuals.map((item) => item.text_en))
    expect(shown.join(' ')).toContain('name on the slip had matched your KYC name (score 85 or more)')
  })

  it('shows a fixture sentence unchanged, whatever it says', async () => {
    const receipt = await anilReceipt()
    const sentence = 'One test sentence, with ₹ and a number 7, that no code could have built.'
    stubReceipt({ ...receipt, counterfactuals: [{ ...receipt.counterfactuals[0], text_en: sentence }] })
    await openReceipt(await session('monsoon', '17:05'))
    expect(text('receipt-counterfactual')).toBe(sentence)
  })

  it('leaves the row out when the receipt carries no counterfactual', async () => {
    const receipt = await anilReceipt()
    stubReceipt({ ...receipt, counterfactuals: [] })
    await openReceipt(await session('monsoon', '17:05'))
    expect(screen.queryByTestId('receipt-counterfactual')).toBeNull()
    expect(screen.queryByTestId('receipt-what-changes')).toBeNull()
  })
})

describe('a number with no source (AC-28)', () => {
  it('reads Source missing on that row, and only on that row', async () => {
    const receipt = await anilReceipt()
    const facts = receipt.explanation.facts.map((fact) => (fact.key === 'share' ? { ...fact, sources: [] } : fact))
    renderContent({ ...receipt, explanation: { ...receipt.explanation, facts } })
    expect(within(screen.getByTestId('receipt-source-share')).getByTestId('source-missing').textContent).toBe('Source missing')
    expect(screen.getAllByTestId('source-missing')).toHaveLength(1)
    expect(within(screen.getByTestId('receipt-source-expected_day')).queryByTestId('source-missing')).toBeNull()
  })

  it('is refused by the parser when it comes from the API, so the screen shows contract_violation', async () => {
    const receipt = await anilReceipt()
    const facts = receipt.explanation.facts.map((fact, index) => (index === 2 ? { ...fact, sources: [] } : fact))
    stubReceipt({ ...receipt, explanation: { ...receipt.explanation, facts } })
    await openReceipt(await session('monsoon', '17:05'), 'D-000142', 'lang=en', 'error')
    expect(text('app-error')).toContain('Error code: contract_violation')
    expect(screen.queryByTestId('receipt-document')).toBeNull()
  })

  it('never happens on the real receipts of the demo', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    expect(screen.queryByTestId('source-missing')).toBeNull()
  })
})

describe('the lender block', () => {
  it("says the lender paused the instalment, never that Chhatri did, and marks the lender SIMULATED", async () => {
    const receipt = await anilReceipt()
    renderContent({ ...receipt, edi: edi({}) })
    const row = screen.getByTestId('receipt-lender')
    expect(row.textContent).toContain('Your lender has paused the ₹600 instalment due on 20 August.')
    expect(row.textContent).toContain('SIMULATED lender')
    expect(document.body.textContent).not.toMatch(/chhatri\s+(has\s+)?paused/i)
  })

  it('reads "Not available" for a refusal and shows no reason code', async () => {
    const receipt = await anilReceipt()
    renderContent({ ...receipt, edi: edi({ status: 'REFUSED', reason_code: 'IN_ARREARS' }) })
    expect(text('receipt-lender')).toContain('Not available. Your instalment is due as usual.')
    expect(document.body.textContent).not.toContain('IN_ARREARS')
    expect(document.body.textContent).not.toMatch(/arrears|overdue/i)
  })

  it('has no lender row while the lender block is off', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    expect(screen.queryByTestId('receipt-lender')).toBeNull()
  })
})

describe('printing (AC-30)', () => {
  it('calls window.print once', async () => {
    const print = stubPrint()
    await openReceipt(await session('monsoon', '17:05'))
    fireEvent.click(screen.getByTestId('receipt-print'))
    expect(print).toHaveBeenCalledTimes(1)
  })

  it('carries the print header, hidden on screen, and keeps every button out of the print', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    const header = screen.getByTestId('receipt-print-header')
    expect(header.textContent).toBe('Chhatri · decision receipt · prototype · SIMULATED data')
    expect(header.className).toContain('hidden')
    expect(header.className).toContain('print:block')
    for (const id of ['receipt-print', 'receipt-checks-toggle']) expect(screen.getByTestId(id).className).toContain('print:hidden')
  })

  it('still prints while offline', async () => {
    const print = stubPrint()
    await openReceipt(await session('monsoon', '17:05'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-receipt').getAttribute('data-state')).toBe('offline'))
    expect((screen.getByTestId('receipt-print') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByTestId('receipt-print'))
    expect(print).toHaveBeenCalledTimes(1)
  })
})

describe('Check the log (AC-31)', () => {
  it('shows the entry count from the audit verify route, under "Verify this decision", and prints the result', async () => {
    const kit = await session('monsoon', '17:05')
    const verify = await kit.api.verifyAudit()
    await openReceipt(kit)
    expect(screen.queryByTestId('receipt-log-result')).toBeNull()
    fireEvent.click(screen.getByTestId('receipt-check-log'))
    await waitFor(() => expect(text('receipt-log-result')).toBe(`Log unbroken, ${verify.entries} entries`))
    expect(screen.getByTestId('receipt-log-result').getAttribute('data-valid')).toBe('true')
    expect(verify.entries).toBeGreaterThan(0)
    expect(screen.getByTestId('receipt-authority').contains(screen.getByTestId('receipt-log-result'))).toBe(true)
    expect(screen.getByTestId('receipt-verify').className).not.toContain('print:hidden')
    expect(within(screen.getByTestId('receipt-audit')).queryByTestId('receipt-check-log')).toBeNull()
    expect(text('receipt-audit')).toContain(`#${(await kit.api.receipt('D-000142')).audit.seq}`)
  })

  it('shows the first broken entry and never hides it', async () => {
    const real = ApiClient.prototype.get
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path === '/api/audit/verify') return Promise.resolve({ valid: false, entries: 9, head_hash: 'abc', first_bad_seq: 4 }) as never
      return real.call(this, path, signal)
    })
    await openReceipt(await session('monsoon', '17:05'))
    fireEvent.click(screen.getByTestId('receipt-check-log'))
    await waitFor(() => expect(text('receipt-log-result')).toBe('The log is broken at entry 4.'))
    expect(screen.getByTestId('receipt-log-result').getAttribute('data-valid')).toBe('false')
  })

  it('says so when the log cannot be checked, and lets the merchant try again', async () => {
    const real = ApiClient.prototype.get
    let failing = true
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path === '/api/audit/verify' && failing) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    await openReceipt(await session('monsoon', '17:05'))
    fireEvent.click(screen.getByTestId('receipt-check-log'))
    await waitFor(() => expect(text('receipt-log-error')).toContain('Something went wrong. Try again.'))
    failing = false
    fireEvent.click(screen.getByTestId('receipt-check-log'))
    await waitFor(() => expect(text('receipt-log-result')).toMatch(/^Log unbroken, \d+ entries$/))
  })

  it('is disabled with a reason while offline', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-receipt').getAttribute('data-state')).toBe('offline'))
    expect((screen.getByTestId('receipt-check-log') as HTMLButtonElement).disabled).toBe(true)
    expect(text('screen-receipt')).toContain('This needs the internet. Please try again when you are online.')
  })
})

describe('what this screen leads to', () => {
  it('says disagree next on a paid claim, and the bar opens the claim with the dispute button focused', async () => {
    await openReceipt(await session('monsoon', '17:05'))
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('disagree')
    fireEvent.click(screen.getByTestId('app-nba-action'))
    await screen.findByTestId('screen-claim')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142')
    const button = await screen.findByTestId('claim-dispute-button')
    await waitFor(() => expect(document.activeElement).toBe(button))
  })
})

describe('a receipt that is not there or does not load (AC-40)', () => {
  it('says it could not find an unknown decision and links back to the claims', async () => {
    await openReceipt(await session('monsoon', '17:05'), 'D-999999', 'lang=en', 'error')
    expect(text('app-error')).toContain('We could not find this.')
    expect(within(screen.getByTestId('app-error')).getByRole('link').getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=claims')
    expect(screen.queryByTestId('app-error-retry')).toBeNull()
  })

  it('treats a link with no decision id as not found', async () => {
    const kit = await session('monsoon', '17:05')
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=receipt', kit.backend)
    await waitFor(() => expect(screen.getByTestId('screen-receipt').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('We could not find this.')
  })

  it('shows the generic error with its code, and Retry asks again', async () => {
    const real = ApiClient.prototype.get
    let failing = true
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/receipt') && failing) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    await openReceipt(await session('monsoon', '17:05'), 'D-000142', 'lang=en', 'error')
    expect(text('app-error')).toContain('Error code: internal_error')
    failing = false
    fireEvent.click(screen.getByTestId('app-error-retry'))
    await waitFor(() => expect(screen.getByTestId('screen-receipt').getAttribute('data-state')).toBe('ready'))
  })

  it('draws a skeleton of a document while loading', async () => {
    const kit = await session('monsoon', '17:05')
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142', kit.backend)
    const root = screen.getByTestId('screen-receipt')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    await waitFor(() => expect(root.getAttribute('data-state')).toBe('ready'))
  })
})

/** Case panel parts that read the decision receipt (card 6.1: H13 source chips, H14 counterfactual line, X4 holiday row, K5 dispute labels). */
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Case, Check, Counterfactual, ReceiptEdi, Source } from '../../api/types'
import { CaseDetail } from './CaseDetail'
import { Checks } from './Checks'
import { CounterfactualLine } from './CounterfactualLine'
import { HolidayRow, holidayWords } from './HolidayRow'
import { sourceChipText, sourcesByCode } from './receiptParts'

const SIM: Source = { kind: 'ALERT', label: 'IMD-style nowcast · simulated', ref: 'alert:A-20250818-01', as_of: '2025-08-18T17:30:00+05:30', origin: 'SIMULATED', clause: 'C2' }
const CONFIG: Source = { kind: 'RULES', label: 'Payout rules, pilot-0.1', ref: 'rules:pilot-0.1:area.index_floor_pct', as_of: null, origin: 'CONFIG', clause: 'C2' }
const check = (code: string): Check => ({ code, status: 'PASS', severity: 'HARD', label_en: `${code} label`, detail_en: '', observed: 'seen', required: 'needed' }) as Check
const CF: Counterfactual = {
  id: 'CF-1', kind: 'AMOUNT_SENSITIVITY', actionable: false, changes: [], result: null, verified: true,
  text_en: 'One more point of area drop would add about ₹22.', text_hi: '', sources: [],
}
const EDI: ReceiptEdi = { request_id: 'HR-000001', status: 'GRANTED', reason_code: null, instalment_date: '2025-08-20', instalment_label: '₹600', decided_at: '2025-08-19T17:05:00+05:30', lender: 'Simulated lender (NBFC partner)' }

const noop = () => Promise.resolve()

function dispute(status: Case['status'] = 'OPEN'): Case {
  return {
    id: 'C-2291', kind: 'DISPUTE', status, merchant_id: 'S-0142', merchant_name: 'Anil’s Tea Stall', opened_at: '2025-08-19T17:06:00+05:30', due_by: '2025-08-20T17:06:00+05:30',
    summary_en: 'Anil disputes ₹1,380', resolution: null, resolved_by: null, resolved_at: null, evidence: {}, decision: null,
  } as unknown as Case
}
const view = (kind: Case['kind'], status: Case['status'] = 'OPEN') => render(
  <MemoryRouter>
    <CaseDetail item={{ ...dispute(status), kind }} now="2025-08-19T17:10:00+05:30" officerReady actionError={null} onDecide={noop} onDismissError={noop} />
  </MemoryRouter>,
)

describe('source chips (H13)', () => {
  it('says label, record, time and the origin word, and never "verified"', () => {
    expect(sourceChipText(SIM)).toBe('IMD-style nowcast · simulated · alert:A-20250818-01 · 18 Aug 17:30 · SIMULATED')
    expect(sourceChipText(CONFIG)).toBe('Payout rules, pilot-0.1 · rules:pilot-0.1:area.index_floor_pct · CONFIG')
    expect(sourceChipText(SIM).toLowerCase()).not.toContain('verified')
  })

  it('maps a receipt check code to its sources and renders them in a Source column', () => {
    const receipt = { checks: [{ ...check('ALERT_ACTIVE'), sources: [SIM] }] } as Parameters<typeof sourcesByCode>[0]
    const by = sourcesByCode(receipt)
    render(<Checks checks={[check('ALERT_ACTIVE'), check('NOPE')]} sources={by} />)
    expect(screen.getByRole('columnheader', { name: 'Source' })).toBeTruthy()
    expect(screen.getByText(/alert:A-20250818-01/).textContent).toContain('SIMULATED')
  })

  it('shows no Source column before a receipt exists, and a grey bar while it loads', () => {
    const { container, rerender } = render(<Checks checks={[check('ALERT_ACTIVE')]} />)
    expect(screen.queryByRole('columnheader', { name: 'Source' })).toBeNull()
    rerender(<Checks checks={[check('ALERT_ACTIVE')]} sourcesLoading />)
    expect(container.querySelector('.skeleton')).not.toBeNull()
  })
})

describe('counterfactual line (H14)', () => {
  it('shows the first counterfactual with the re-run note', () => {
    render(<CounterfactualLine counterfactuals={[CF]} />)
    expect(screen.getByText(CF.text_en)).toBeTruthy()
    expect(screen.getByText('checked by re-running the engine')).toBeTruthy()
  })
  it('shows nothing when the receipt carries none', () => {
    const { container } = render(<CounterfactualLine counterfactuals={[]} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('holiday row (X4)', () => {
  it('words every status, refusals with the reason in words', () => {
    expect(holidayWords(EDI)).toBe('Lender granted the holiday: ₹600 due Wed 20 Aug')
    expect(holidayWords({ ...EDI, status: 'REFUSED', reason_code: 'IN_ARREARS' })).toBe('Lender refused the holiday (IN_ARREARS): the loan has an amount overdue')
    expect(holidayWords({ ...EDI, status: 'REFUSED', reason_code: 'NO_ALLOWANCE' })).toContain('your holiday allowance is used up')
    expect(holidayWords({ ...EDI, status: 'NO_RESPONSE' })).toBe('Lender did not answer: the ₹600 instalment stays due')
    expect(holidayWords({ ...EDI, status: 'REQUESTED' })).toBe('Lender asked to pause the ₹600 instalment due Wed 20 Aug')
  })
  it('renders as a labelled row and renders nothing without a request', () => {
    const { rerender, container } = render(<HolidayRow edi={EDI} />)
    expect(screen.getByText('Loan instalment')).toBeTruthy()
    expect(screen.getByText(/Lender granted the holiday/)).toBeTruthy()
    rerender(<HolidayRow edi={null} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('dispute labels (K5)', () => {
  it('names the buttons Confirm payout and Reject dispute with the hint above them', () => {
    view('DISPUTE')
    expect(screen.getByRole('button', { name: 'Confirm payout' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reject dispute' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
    expect(screen.getByText(/The amount cannot change\. Confirming keeps the payout\. Rejecting closes the dispute\./)).toBeTruthy()
  })
  it('keeps Approve and Decline for other cases', () => {
    view('PERSONAL_CLAIM_REVIEW')
    const actions = within(document.body)
    expect(actions.getByRole('button', { name: 'Approve' })).toBeTruthy()
    expect(actions.getByRole('button', { name: 'Decline' })).toBeTruthy()
    expect(actions.queryByText(/cannot change/)).toBeNull()
  })
})

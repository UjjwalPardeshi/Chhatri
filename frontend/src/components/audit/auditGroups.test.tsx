/** Audit table helpers (SPEC §11 tamper-evident log, §20 "Audit"). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { AuditEntry } from '../../api/types'
import { AuditTable } from './AuditTable'
import { groupByMinute, isMoneyAction } from './auditGroups'
import { actorLabel, describeEntry, searchText, subjectLabel } from './auditText'

const entry = (seq: number, hhmm: string, action: string): AuditEntry =>
  ({ seq, at: `2025-08-19T${hhmm}:00+05:30`, actor: 'system', action, subject_type: 'x', subject_id: `X-${seq}`, data: {}, hash: `h${seq}`.padEnd(64, '0'), prev_hash: `h${seq - 1}`.padEnd(64, '0') }) as AuditEntry

const NEWEST_FIRST = [entry(3, '17:05', 'instalment.pause'), entry(2, '17:04', 'payout.credited'), entry(1, '17:04', 'message.sent')]

describe('audit groups', () => {
  it('groups entries by simulated minute in the order shown', () => {
    expect(groupByMinute(NEWEST_FIRST).map((g) => [g.label, g.items.map((e) => e.seq)])).toEqual([
      ['19 Aug 2025 · 17:05', [3]],
      ['19 Aug 2025 · 17:04', [2, 1]],
    ])
    expect(groupByMinute([])).toEqual([])
  })

  it('marks money actions', () => {
    expect(isMoneyAction('payout.credited')).toBe(true)
    expect(isMoneyAction('instalment.pause')).toBe(true)
    expect(isMoneyAction('message.sent')).toBe(false)
  })

  it('says what happened in plain words, with the raw code kept for search (X4 answers included)', () => {
    expect(describeEntry({ ...entry(1, '17:05', 'instalment.holiday_request'), data: { amount_paise: 45000, merchant_id: 'S-0232', instalment_date: '2025-08-20', loan_id: 'LN-0232' } })).toEqual({
      text: 'Asked the lender to move the ₹450 instalment of merchant S-0232',
      detail: 'due 20 Aug 2025 · loan LN-0232',
    })
    expect(describeEntry({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'GRANTED', merchant_id: 'S-0232', moved_to: 'END_OF_TENURE', penalty_paise: 0 } })).toEqual({
      text: 'Lender agreed to move the instalment of merchant S-0232',
      detail: 'moved to end of tenure · no penalty',
    })
    expect(describeEntry({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'REFUSED', reason_code: 'IN_ARREARS' } }).detail).toBe('loan in arrears')
    expect(describeEntry({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'NO_RESPONSE' } }).text).toBe('Lender did not answer about the instalment of the merchant')
    expect(describeEntry({ ...entry(4, '17:04', 'payout.credit'), data: { amount_paise: 141700, merchant_id: 'S-0228', reference: 'CHHATRI-SIM-P-000001' } })).toEqual({
      text: '₹1,417 credited to merchant S-0228',
      detail: 'reference CHHATRI-SIM-P-000001',
    })
    expect(describeEntry({ ...entry(5, '17:04', 'message.outbound'), data: { channel: 'TELEGRAM', key: 'AREA_PAYOUT_INTRO', merchant_id: 'S-0142' } }).detail).toBe('Telegram · area payout intro')
    expect(describeEntry(entry(6, '17:04', 'something.new_here'))).toEqual({ text: 'Something new here', detail: null })
    expect(actorLabel('workflow:payout')).toBe('Payout workflow')
    expect(actorLabel('officer:officer')).toBe('Claims officer')
    expect(actorLabel('merchant:S-0142')).toBe('Merchant S-0142')
    expect(subjectLabel('instalment_pause')).toBe('Instalment pause')
    expect(searchText({ ...entry(7, '17:04', 'payout.credit'), data: { amount_paise: 100, merchant_id: 'S-1' } })).toContain('payout.credit')
  })

  it('marks only the pause itself as an instalment that moved, not the ask or the answer (X4)', () => {
    expect(isMoneyAction('instalment.pause')).toBe(true)
    expect(isMoneyAction('instalment.holiday_request')).toBe(false)
    expect(isMoneyAction('instalment.holiday_decision')).toBe(false)
    expect(isMoneyAction('instalment.holiday_skipped')).toBe(false)
  })

  it('shows plain words in the table, keeps the raw code in the tooltip and marks one money row', () => {
    const entries = [entry(3, '17:05', 'instalment.pause'), { ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'GRANTED' } }, entry(1, '17:05', 'instalment.holiday_request')]
    const { container } = render(<AuditTable entries={entries} verified={0} />)
    expect(screen.getByText('Asked the lender to move the instalment of the merchant')).toBeTruthy()
    expect(screen.getByText('Lender agreed to move the instalment of the merchant')).toBeTruthy()
    expect(screen.getByText('Paused the instalment of the merchant').closest('td')?.getAttribute('title')).toBe('instalment.pause')
    expect(screen.getAllByText('Chhatri system')).toHaveLength(3)
    expect(container.querySelectorAll('[data-money="true"]')).toHaveLength(1)
    expect(screen.queryByText('instalment.holiday_request', { exact: false })).toBeNull()
  })

  it('links a hash to the next entry’s previous hash on hover and checks rows after a verify', () => {
    const { container, rerender } = render(<AuditTable entries={NEWEST_FIRST} verified={0} />)
    expect(screen.getAllByRole('rowheader').map((h) => h.textContent)).toEqual(['19 Aug 2025 · 17:05', '19 Aug 2025 · 17:04'])
    fireEvent.mouseEnter(screen.getByText('2', { selector: 'td' }).closest('tr') as Element)
    expect([...container.querySelectorAll('[data-match="true"]')].map((c) => c.getAttribute('data-label'))).toEqual(['Previous', 'Fingerprint'])
    expect(container.querySelectorAll('.audit-row__check')).toHaveLength(0)
    rerender(<AuditTable entries={NEWEST_FIRST} verified={1} />)
    expect(container.querySelectorAll('.audit-row__check')).toHaveLength(3)
    expect(container.querySelectorAll('[data-money="true"]')).toHaveLength(2)
  })
})

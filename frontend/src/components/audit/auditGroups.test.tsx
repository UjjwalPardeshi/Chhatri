/** Audit table helpers (SPEC §11 tamper-evident log, §20 "Audit"). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { AuditEntry } from '../../api/types'
import { AuditTable } from './AuditTable'
import { actionName, groupByMinute, isMoneyAction } from './auditGroups'

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

  it('names the lender’s request and answer, and says so when there was no answer (X4)', () => {
    expect(actionName(entry(1, '17:05', 'instalment.holiday_request'))).toBe('Lender asked')
    expect(actionName({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'GRANTED' } })).toBe('Lender answered')
    expect(actionName({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'REFUSED', reason_code: 'IN_ARREARS' } })).toBe('Lender answered')
    expect(actionName({ ...entry(2, '17:05', 'instalment.holiday_decision'), data: { decision: 'NO_RESPONSE' } })).toBe('Lender did not answer')
    expect(actionName(entry(3, '17:05', 'instalment.pause'))).toBeNull()
    expect(actionName(entry(4, '17:04', 'payout.credited'))).toBeNull()
  })

  it('marks only the pause itself as an instalment that moved, not the ask or the answer (X4)', () => {
    expect(isMoneyAction('instalment.pause')).toBe(true)
    expect(isMoneyAction('instalment.holiday_request')).toBe(false)
    expect(isMoneyAction('instalment.holiday_decision')).toBe(false)
    expect(isMoneyAction('instalment.holiday_skipped')).toBe(false)
  })

  it('shows the plain name beside the raw action in the table and marks one money row', () => {
    const entries = [entry(3, '17:05', 'instalment.pause'), entry(2, '17:05', 'instalment.holiday_decision'), entry(1, '17:05', 'instalment.holiday_request')]
    const { container } = render(<AuditTable entries={entries} verified={0} />)
    expect(screen.getByText('Lender asked')).toBeTruthy()
    expect(screen.getByText('Lender answered')).toBeTruthy()
    expect(container.querySelectorAll('[data-money="true"]')).toHaveLength(1)
    expect(screen.getByText('instalment.holiday_request', { exact: false })).toBeTruthy()
  })

  it('links a hash to the next entry’s previous hash on hover and checks rows after a verify', () => {
    const { container, rerender } = render(<AuditTable entries={NEWEST_FIRST} verified={0} />)
    expect(screen.getAllByRole('rowheader').map((h) => h.textContent)).toEqual(['19 Aug 2025 · 17:05', '19 Aug 2025 · 17:04'])
    fireEvent.mouseEnter(screen.getByText('2', { selector: 'td' }).closest('tr') as Element)
    expect([...container.querySelectorAll('[data-match="true"]')].map((c) => c.getAttribute('data-label'))).toEqual(['Previous', 'Hash'])
    expect(container.querySelectorAll('.audit-row__check')).toHaveLength(0)
    rerender(<AuditTable entries={NEWEST_FIRST} verified={1} />)
    expect(container.querySelectorAll('.audit-row__check')).toHaveLength(3)
    expect(container.querySelectorAll('[data-money="true"]')).toHaveLength(2)
  })
})

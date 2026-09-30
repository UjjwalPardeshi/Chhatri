/** Audit table helpers (SPEC §11 tamper-evident log, §20 "Audit"). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { AuditEntry } from '../../api/types'
import { AuditTable } from './AuditTable'
import { groupByMinute, isMoneyAction } from './auditGroups'

const entry = (seq: number, hhmm: string, action: string): AuditEntry =>
  ({ seq, at: `2025-08-19T${hhmm}:00+05:30`, actor: 'system', action, subject_type: 'x', subject_id: `X-${seq}`, hash: `h${seq}`.padEnd(64, '0'), prev_hash: `h${seq - 1}`.padEnd(64, '0') }) as AuditEntry

const NEWEST_FIRST = [entry(3, '17:05', 'instalment.paused'), entry(2, '17:04', 'payout.credited'), entry(1, '17:04', 'message.sent')]

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
    expect(isMoneyAction('instalment.paused')).toBe(true)
    expect(isMoneyAction('message.sent')).toBe(false)
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

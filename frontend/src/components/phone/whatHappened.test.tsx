/** "What happened" beside the phone (SPEC §17.2 timeline, §13 INSTALMENT_PAUSED). */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Decision, HolidayRequest, Message, Payout } from '../../api/types'
import { COMPACT_BARS, Waveform } from './Waveform'
import { happenedSteps } from './whatHappened'
import { WhatHappened } from './WhatHappened'

const at = (hhmm: string) => `2025-08-19T${hhmm}:00+05:30`
const DECISION = { outcome: 'APPROVED', amount_label: '₹1,380', decided_at: at('17:00'), decided_by: 'policy-engine' } as Decision
const PAYOUT = { amount_label: '₹1,380', status: 'CREDITED', credited_at: at('17:04'), created_at: at('17:00') } as Payout
const PAUSE = { direction: 'OUTBOUND', text_en: "Tomorrow's ₹600 instalment is paused.", created_at: at('17:05') } as Message
const REQUEST = { id: 'HR-000001', status: 'GRANTED', reason_code: null, instalment_label: '₹600', instalment_date: '2025-08-20', requested_at: at('17:05'), decided_at: at('17:05') } as HolidayRequest

/** The text of the lender's answer step for a refusal with `reason`. */
const detail = (reason: HolidayRequest['reason_code']) =>
  happenedSteps({ decisions: [], payouts: [], holiday_requests: [{ ...REQUEST, status: 'REFUSED', reason_code: reason }] }, []).at(-1)?.detail

describe('what happened', () => {
  it('reads the decision, the credit and the instalment pause, in order', () => {
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT] }, [PAUSE])
    expect(steps.map((s) => s.title)).toEqual(['Decision APPROVED', '₹1,380 credited', 'Tomorrow’s ₹600 instalment paused'])
    render(<WhatHappened steps={steps} />)
    expect(screen.getByText('17:04')).toBeTruthy()
  })

  it('reads today’s pause too (the illness replays run on the paused day) and names the policy engine plainly', () => {
    const today = { ...PAUSE, text_en: "Today's ₹600 instalment is paused." }
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT] }, [today])
    expect(steps.at(-1)?.title).toBe('Today’s ₹600 instalment paused')
    expect(steps[0].detail).toBe('₹1,380 · policy engine')
  })

  it('shows only what has happened so far', () => {
    expect(happenedSteps({ decisions: [], payouts: [] }, [])).toEqual([])
    const pending = happenedSteps({ decisions: [{ ...DECISION, outcome: 'REFERRED', decided_by: 'officer:officer' }], payouts: [{ ...PAYOUT, status: 'PENDING', credited_at: null }] }, [])
    expect(pending.map((s) => [s.title, s.tone])).toEqual([
      ['Decision REFERRED', 'amber'],
      ['₹1,380 on its way', 'amber'],
    ])
    expect(pending[0].detail).toBe('₹1,380 · claims officer')
    const { container } = render(<WhatHappened steps={[]} />)
    expect(container.textContent).toBe('')
  })

  it('reads the lender asking and answering when the merchant has holiday requests (X4)', () => {
    const lender = { ...PAUSE, text_en: "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty." }
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT], holiday_requests: [REQUEST] }, [lender])
    expect(steps.map((s) => s.title)).toEqual(['Decision APPROVED', '₹1,380 credited', 'Lender asked', 'Lender answered'])
    expect(steps[2]).toMatchObject({ key: 'asked', at: at('17:05'), detail: 'to pause the ₹600 instalment due Wed 20 Aug', tone: 'blue' })
    expect(steps[3]).toMatchObject({ key: 'answered', detail: 'paused · moved to the end of the loan, no penalty', tone: 'blue' })
  })

  it('says plainly when the lender refused and why, and does not call it a pause', () => {
    const refused = { ...REQUEST, status: 'REFUSED', reason_code: 'IN_ARREARS' } as HolidayRequest
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT], holiday_requests: [refused] }, [])
    expect(steps.at(-1)).toMatchObject({ title: 'Lender answered', detail: 'could not pause · the loan has an amount overdue', tone: 'amber' })
    expect(steps.map((s) => s.key)).not.toContain('pause')
  })

  it('names each refusal reason in the lender’s terms', () => {
    expect(detail('FLAG_OFF')).toBe('could not pause · this loan is not part of the holiday scheme')
    expect(detail('NOT_ACTIVE')).toBe('could not pause · the loan is not active')
    expect(detail('NO_ALLOWANCE')).toBe('could not pause · your holiday allowance is used up')
    expect(detail(null)).toBe('could not pause')
  })

  it('says plainly when the lender gave no answer: the instalment stays due and the payout is untouched', () => {
    const silent = { ...REQUEST, status: 'NO_RESPONSE', reason_code: null } as HolidayRequest
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT], holiday_requests: [silent] }, [])
    expect(steps.at(-1)).toMatchObject({ key: 'answered', title: 'Lender did not answer', detail: 'the instalment stays due · the payout is not affected', tone: 'amber' })
  })

  it('shows only the request while the lender has not answered', () => {
    const waiting = { ...REQUEST, status: 'REQUESTED', decided_at: null } as HolidayRequest
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT], holiday_requests: [waiting] }, [])
    expect(steps.map((s) => s.title)).toEqual(['Decision APPROVED', '₹1,380 credited', 'Lender asked'])
  })

  it('keeps the BUILT pause step when there are no holiday requests (flag off)', () => {
    const steps = happenedSteps({ decisions: [DECISION], payouts: [PAYOUT], holiday_requests: [] }, [PAUSE])
    expect(steps.map((s) => s.title)).toEqual(['Decision APPROVED', '₹1,380 credited', 'Tomorrow’s ₹600 instalment paused'])
  })

  it('draws a compact waveform for Chhatri’s spoken lines', () => {
    const { container } = render(<Waveform seed="M-1" seconds={3} playKey={0} compact />)
    expect(container.querySelectorAll('.wave--compact .wave__bars span')).toHaveLength(COMPACT_BARS)
  })
})

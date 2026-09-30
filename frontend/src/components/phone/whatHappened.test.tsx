/** "What happened" beside the phone (SPEC §17.2 timeline, §13 INSTALMENT_PAUSED). */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Decision, Message, Payout } from '../../api/types'
import { COMPACT_BARS, Waveform } from './Waveform'
import { happenedSteps } from './whatHappened'
import { WhatHappened } from './WhatHappened'

const at = (hhmm: string) => `2025-08-19T${hhmm}:00+05:30`
const DECISION = { outcome: 'APPROVED', amount_label: '₹1,380', decided_at: at('17:00'), decided_by: 'policy-engine' } as Decision
const PAYOUT = { amount_label: '₹1,380', status: 'CREDITED', credited_at: at('17:04'), created_at: at('17:00') } as Payout
const PAUSE = { direction: 'OUTBOUND', text_en: "Tomorrow's ₹600 instalment is paused.", created_at: at('17:05') } as Message

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

  it('draws a compact waveform for Chhatri’s spoken lines', () => {
    const { container } = render(<Waveform seed="M-1" seconds={3} playKey={0} compact />)
    expect(container.querySelectorAll('.wave--compact .wave__bars span')).toHaveLength(COMPACT_BARS)
  })
})

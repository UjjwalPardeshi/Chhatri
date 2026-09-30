/** Settling a paused replay after a decision (B1/B2, SPEC §10). */
import { describe, expect, it } from 'vitest'

import type { Decision, Payout } from '../api/types'
import { awaitingCredit, settleMinutes } from './useSettle'

const decision = (id: string, outcome: Decision['outcome'], amount = 150_000) => ({ id, outcome, amount_paise: amount }) as Decision
const payout = (decisionId: string, status: Payout['status']) => ({ decision_id: decisionId, status }) as Payout

describe('settle', () => {
  it('steps to the last payout-workflow offset of the published rules', () => {
    expect(settleMinutes({ payout_rail_delay_minutes: 4, instalment_pause_delay_minutes: 5 })).toBe(5)
    expect(settleMinutes({ payout_rail_delay_minutes: 6, instalment_pause_delay_minutes: 5 })).toBe(6)
    expect(settleMinutes({ payout_rail_delay_minutes: 4 })).toBeNull()
    expect(settleMinutes(null)).toBeNull()
  })

  it('waits only for approved money that is not credited yet', () => {
    expect(awaitingCredit({ decisions: [decision('D-1', 'APPROVED')], payouts: [] })).toBe(true)
    expect(awaitingCredit({ decisions: [decision('D-1', 'APPROVED')], payouts: [payout('D-1', 'PENDING')] })).toBe(true)
    expect(awaitingCredit({ decisions: [decision('D-1', 'APPROVED')], payouts: [payout('D-1', 'CREDITED')] })).toBe(false)
    expect(awaitingCredit({ decisions: [decision('D-1', 'REFERRED')], payouts: [] })).toBe(false)
    expect(awaitingCredit({ decisions: [decision('D-1', 'APPROVED', 0)], payouts: [] })).toBe(false)
    expect(awaitingCredit({ decisions: [], payouts: [] })).toBe(false)
  })
})

/** What happens next after a payout (fs-04 S5): read from the receipt and the cover only; a step with no data is left out. */
import { describe, expect, it } from 'vitest'

import type { Cover, Receipt, ReceiptEdi } from '../../api/types'
import { session } from '../../test/claimScenes'
import { parseCover, parseReceipt } from '../api/parse'
import { lineShown } from '../components/StepperLine'
import type { Lang } from '../lib/lang'
import { nextSteps, type NextStep } from './ClaimNextSteps'

async function anil(): Promise<{ receipt: Receipt; cover: Cover }> {
  const kit = await session('monsoon', '17:05')
  const receipt = parseReceipt(await kit.api.receipt('D-000142'))
  const cover = parseCover(await kit.api.cover('S-0142'))
  kit.backend.dispose()
  return { receipt, cover }
}

const ids = (steps: readonly NextStep[]) => steps.map((step) => step.id)
const words = (step: NextStep | undefined, lang: Lang = 'en') => (step ? lineShown(step.line, lang)?.text : undefined)
const find = (steps: readonly NextStep[], id: NextStep['id']) => steps.find((step) => step.id === id)

const GRANTED: ReceiptEdi = {
  request_id: 'HR-000001',
  status: 'GRANTED',
  reason_code: null,
  instalment_date: '2025-08-20',
  instalment_label: '₹600',
  decided_at: '2025-08-19T17:05:00+05:30',
  lender: 'Demo Lender',
}

describe('nextSteps', () => {
  it("says the money, the dispute path with its clock and the cover, in order, in the receipt's and the cover's words", async () => {
    const { receipt, cover } = await anil()
    const steps = nextSteps({ receipt, cover, canDispute: true }, 'en')
    expect(ids(steps)).toEqual(['money', 'wrong', 'cover'])
    expect(words(steps[0])).toBe(`${receipt.payout?.amount_label} was credited with your settlement on 19 August, 17:04.`)
    expect(steps[0].simulated).toBe('payment')
    expect(words(steps[1])).toBe('If the amount looks wrong, tap This is wrong.')
    expect(steps[1].note === null ? null : lineShown(steps[1].note, 'en')?.text).toBe(`We reply within ${receipt.grievance.first_step_hours} hours.`)
    expect(words(steps[2])).toBe('Your cover continues. The premium is paid up to 22 August.')
  })

  it('has no list at all until the payout is credited', async () => {
    const { receipt, cover } = await anil()
    const pending = { ...receipt, payout: receipt.payout && { ...receipt.payout, status: 'PENDING' as const, credited_at: null } }
    expect(nextSteps({ receipt: pending, cover, canDispute: true }, 'en')).toEqual([])
    expect(nextSteps({ receipt: { ...receipt, payout: null }, cover, canDispute: true }, 'en')).toEqual([])
  })

  it("puts the lender's answer second, worded by the fixed line for that answer, and leaves it out with no lender block", async () => {
    const { receipt, cover } = await anil()
    const granted = nextSteps({ receipt: { ...receipt, edi: GRANTED }, cover, canDispute: true }, 'en')
    expect(ids(granted)).toEqual(['money', 'lender', 'wrong', 'cover'])
    expect(words(find(granted, 'lender'))).toBe('Your lender has paused the ₹600 instalment due on 20 August. It moves to the end of your loan with no penalty.')
    expect(find(granted, 'lender')?.simulated).toBe('lender')
    const refused = nextSteps({ receipt: { ...receipt, edi: { ...GRANTED, status: 'REFUSED', reason_code: 'NO_ALLOWANCE' } }, cover, canDispute: true }, 'en')
    expect(words(find(refused, 'lender'))).toBe('Not available. Your instalment is due as usual.')
    expect(find(nextSteps({ receipt: { ...receipt, edi: null }, cover, canDispute: true }, 'en'), 'lender')).toBeUndefined()
  })

  it('offers the dispute path only where the screen offers the button and the receipt allows it, with the clock only when there is one', async () => {
    const { receipt, cover } = await anil()
    expect(find(nextSteps({ receipt, cover, canDispute: false }, 'en'), 'wrong')).toBeUndefined()
    const closed = { ...receipt, grievance: { ...receipt.grievance, dispute_allowed: false } }
    expect(find(nextSteps({ receipt: closed, cover, canDispute: true }, 'en'), 'wrong')).toBeUndefined()
    const noClock = { ...receipt, grievance: { ...receipt.grievance, first_step_hours: 0 } }
    const wrong = find(nextSteps({ receipt: noClock, cover, canDispute: true }, 'en'), 'wrong')
    expect(words(wrong)).toBe('If the amount looks wrong, tap This is wrong.')
    expect(wrong?.note).toBeNull()
  })

  it('says the cover continues only while it is active and paid ahead', async () => {
    const { receipt, cover } = await anil()
    const coverStep = (shown: Cover | null) => find(nextSteps({ receipt, cover: shown, canDispute: true }, 'en'), 'cover')
    expect(coverStep(cover)).toBeDefined()
    expect(coverStep(null)).toBeUndefined()
    expect(coverStep({ ...cover, status: 'LAPSED' })).toBeUndefined()
    expect(coverStep({ ...cover, premium_due: true })).toBeUndefined()
    expect(coverStep({ ...cover, prepaid_through: null })).toBeUndefined()
  })

  it('words every step in Hindi and Marathi, with the API labels unchanged', async () => {
    const { receipt, cover } = await anil()
    for (const lang of ['hi', 'mr'] as const) {
      const steps = nextSteps({ receipt: { ...receipt, edi: GRANTED }, cover, canDispute: true }, lang)
      expect(ids(steps)).toEqual(['money', 'lender', 'wrong', 'cover'])
      expect(words(steps[0], lang)).toContain(receipt.payout?.amount_label ?? '')
      expect(words(steps[1], lang)).toContain('₹600')
      for (const step of steps) expect(words(step, lang)).toMatch(/[ऀ-ॿ]/)
    }
  })
})

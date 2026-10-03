/**
 * Scenario jumps that send a sample slip (deck `reviewCase`): with the slip pre-check on, the photo is only read, so the
 * launcher answers for the merchant as the stage script does: "Yes, this is right" on the READY card, then Yes to the
 * doctor question (design 2.4). Without a READY card (the pre-check off) nothing more is sent.
 */
import { describe, expect, it, vi } from 'vitest'

import type { Api } from '../api/endpoints'
import { AWAITING_CONSENT_RESPONSE, CONFIRMED_RESPONSE } from '../miniapp/api/precheckFixtures'
import { runAction } from './useLaunch'

const readyCard = { precheck_id: 'PC-000002', status: 'READY', slots: [], checklist: [], actions: [] }
const message = (card: unknown, direction = 'OUTBOUND') => ({ id: 'M-1', merchant_id: 'S-0142', direction, kind: 'TEXT', card, meta: {} })

function fakeApi(photoReply: unknown[], answers: unknown[]) {
  const confirm = vi.fn<(id: string, pc: string, action: string) => Promise<unknown>>(async () => answers.shift())
  const api = { sendSampleSlip: vi.fn<() => Promise<unknown[]>>(async () => photoReply), sendVoiceDemo: vi.fn<() => Promise<unknown[]>>(async () => []), confirmSlipPrecheck: confirm }
  return { api: api as unknown as Api, confirm }
}

describe('runAction (launcher steps)', () => {
  it('confirms the READY slip and then says Yes to the doctor question', async () => {
    const { api, confirm } = fakeApi([message(null, 'INBOUND'), message(readyCard)], [{ ...AWAITING_CONSENT_RESPONSE, precheck_id: 'PC-000002', consent: { ...AWAITING_CONSENT_RESPONSE.consent, precheck_id: 'PC-000002' } }, CONFIRMED_RESPONSE])
    await runAction(api, { kind: 'sample', merchant: 'S-0142', file: 'mismatch_admission_slip.png' })
    expect(confirm.mock.calls).toEqual([
      ['S-0142', 'PC-000002', 'CONFIRM'],
      ['S-0142', 'PC-000002', 'CONSENT_YES'],
    ])
  })

  it('stops after CONFIRM when the doctor rule is off (the claim is filed at once)', async () => {
    const { api, confirm } = fakeApi([message(readyCard)], [CONFIRMED_RESPONSE])
    await runAction(api, { kind: 'sample', merchant: 'S-0142', file: 'anil_admission_slip.png' })
    expect(confirm).toHaveBeenCalledTimes(1)
  })

  it('sends nothing more when the photo was filed directly (no pre-check card)', async () => {
    const { api, confirm } = fakeApi([message(null, 'INBOUND'), message(null)], [])
    await runAction(api, { kind: 'sample', merchant: 'S-0142', file: 'anil_admission_slip.png' })
    expect(confirm).not.toHaveBeenCalled()
  })
})

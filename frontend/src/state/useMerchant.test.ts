/** Which live events refresh a merchant (SPEC §19.1), and explanation lead splitting (§17.2). */
import { describe, expect, it } from 'vitest'

import type { SseEvent } from '../api/types'
import { splitLead } from '../components/panel/Explanations'
import { toApiError } from './useAsync'
import { eventMerchantId } from './useMerchant'

const ev = (type: string, data: unknown) => ({ id: '1', at: '', type, data }) as SseEvent
const m = { merchant_id: 'S-0142' }

describe('eventMerchantId', () => {
  it('reads the merchant from every merchant-scoped event', () => {
    expect(eventMerchantId(ev('payout', { payout: m }))).toBe('S-0142')
    expect(eventMerchantId(ev('decision', { decision: m }))).toBe('S-0142')
    expect(eventMerchantId(ev('instalment', { pause: m }))).toBe('S-0142')
    expect(eventMerchantId(ev('message', { message: m }))).toBe('S-0142')
    expect(eventMerchantId(ev('case', { case: m }))).toBe('S-0142')
    expect(eventMerchantId(ev('soundbox', m))).toBe('S-0142')
    expect(eventMerchantId(ev('kpis', {}))).toBeNull()
  })
})

describe('helpers', () => {
  it('splits an explanation at its first colon', () => {
    expect(splitLead('Why Zone 9 got nothing: slow day')).toEqual({ lead: 'Why Zone 9 got nothing:', rest: ' slow day' })
    expect(splitLead('no colon')).toEqual({ lead: '', rest: 'no colon' })
  })

  it('wraps unknown errors as CLIENT_ERROR', () => {
    expect(toApiError(new Error('x'))).toMatchObject({ code: 'CLIENT_ERROR', message: 'x' })
    expect(toApiError('y')).toMatchObject({ code: 'CLIENT_ERROR', message: 'y' })
  })
})

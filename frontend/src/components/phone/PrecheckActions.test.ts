import { describe, expect, it } from 'vitest'

import type { Message } from '../../api/types'
import { openPrecheck } from './PrecheckActions'

function message(card: unknown): Message {
  return { id: 'M-1', merchant_id: 'S-0142', direction: 'OUTBOUND', channel: 'SIMULATOR', kind: 'TEXT', text_hi: null, text_en: 'Is this right?', audio_url: null, media_url: null, card, created_at: '2025-08-21T11:25:00+05:30', meta: {} } as unknown as Message
}

describe('openPrecheck', () => {
  it('finds a READY pre-check card', () => {
    expect(openPrecheck(message({ precheck_id: 'PC-000001', status: 'READY' }))?.precheck_id).toBe('PC-000001')
  })
  it.each([null, {}, { precheck_id: 'PC-000001', status: 'RETAKE' }, { precheck_id: 7, status: 'READY' }, 'text'])('ignores %j', (card) => {
    expect(openPrecheck(message(card))).toBeNull()
  })
})

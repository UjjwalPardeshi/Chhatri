/** Mock Ask Chhatri and voice routes (data-model 5.2 and 5.11): flags, labels, grounding, the scam and hand-off answers, and the 409 for unconfirmed chips. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from './backend'
import { testApi } from './testkit'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri,n4_voice'))
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

async function setup(seek = '17:05') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek(seek)
  return kit.api
}

const OGG = new Uint8Array([0x4f, 0x67, 0x67, 0x53, 0, 0, 0, 0, 0, 0, 0, 0])

describe('POST /api/merchants/{id}/ask', () => {
  it('answers "why this amount" from the merchant decision, with sourced facts and a SIMULATED mock label', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'मुझे इतने ही पैसे क्यों मिले?', lang: 'hi' })
    expect(answer).toMatchObject({ intent: 'WHY_AMOUNT', lang: 'hi', mode: 'SIMULATED', provider: 'mock', fallback_reason: 'MOCK_BACKEND', handoff: false, scam_warning: false })
    expect(answer.next_action.kind).toBe('SEE_CLAIM')
    expect(answer.clauses.map((c) => c.id)).toContain('C4.1')
    expect(answer.facts_used.length).toBeGreaterThan(0)
    for (const f of answer.facts_used) expect(f.sources.length).toBeGreaterThan(0)
    expect(answer.answer).toMatch(/[ऀ-ॿ]/)
    expect(answer.answer_en).not.toMatch(/[ऀ-ॿ]/)
  })

  it('answers in English when asked to', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'Why did I get this amount?', lang: 'en' })
    expect(answer.answer).toBe(answer.answer_en)
  })

  it('answers a clause question from the rules numbers, never from a number of its own', async () => {
    const api = await setup()
    const waiting = await api.ask('S-0142', { question: 'What is the waiting period?', lang: 'en' })
    expect(waiting.answer).toContain('7 days')
    expect(waiting.clauses.map((c) => c.id)).toEqual(['C5'])
    const limit = await api.ask('S-0142', { question: 'What is the yearly limit?', lang: 'en' })
    expect(limit.answer).toContain('₹30,000')
    expect(limit.clauses.map((c) => c.id)).toEqual(['C4.3'])
  })

  it('warns about a scam and still answers, with Ask again as the next step', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'Someone asked for my OTP to pay my claim', lang: 'en' })
    expect(answer.scam_warning).toBe(true)
    expect(answer.answer).toContain('does not ask for your OTP')
    expect(answer.next_action.kind).toBe('ASK_AGAIN')
  })

  it('hands an unknown question to the team', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'Can you buy me a car?', lang: 'en' })
    expect(answer).toMatchObject({ handoff: true, intent: 'UNKNOWN' })
    expect(answer.next_action.kind).toBe('TALK_TO_TEAM')
  })

  it('opens a dispute case when the loss was bigger', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'My loss was bigger', lang: 'en' })
    expect(answer.case_id).toMatch(/^C-\d+$/)
    expect(answer.next_action.kind).toBe('TRACK_CASE')
  })

  it('never writes the word null in a Hindi dispute answer (the case chip is English in every language)', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'मेरा नुकसान ज़्यादा हुआ', lang: 'hi' })
    expect(answer.answer).not.toContain('null')
    expect(answer.answer).toMatch(/Sent to a claims officer · case C-\d+/)
  })

  it('returns the open case for a second "bigger" question instead of opening another', async () => {
    const api = await setup()
    const first = await api.ask('S-0142', { question: 'My loss was bigger', lang: 'en' })
    const second = await api.ask('S-0142', { question: 'My loss was bigger', lang: 'en' })
    expect(second.case_id).toBe(first.case_id)
    expect(second.answer_en).toContain('already with our team')
    expect((await api.cases('ALL')).filter((c) => c.kind === 'DISPUTE')).toHaveLength(1)
  })

  it('numbers answers AQ-000001, AQ-000002 and starts again after a scenario load', async () => {
    const api = await setup()
    expect((await api.ask('S-0142', { question: 'hello', lang: 'en' })).ask_id).toBe('AQ-000001')
    expect((await api.ask('S-0142', { question: 'hello', lang: 'en' })).ask_id).toBe('AQ-000002')
    await api.load('monsoon')
    expect((await api.ask('S-0142', { question: 'hello', lang: 'en' })).ask_id).toBe('AQ-000001')
  })

  it('refuses an empty question, an over-long question and a bad language', async () => {
    const api = await setup()
    await expect(api.client.post('/api/merchants/S-0142/ask', { question: '  ' })).rejects.toMatchObject({ status: 422, code: 'validation_error' })
    await expect(api.client.post('/api/merchants/S-0142/ask', { question: 'a'.repeat(501) })).rejects.toMatchObject({ status: 422 })
    await expect(api.client.post('/api/merchants/S-0142/ask', { question: 'hi', lang: 'mr' })).rejects.toMatchObject({ status: 422 })
    await expect(api.client.post('/api/merchants/S-9999/ask', { question: 'hi' })).rejects.toMatchObject({ status: 404 })
  })

  it('is not found while the flag is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const api = await setup()
    await expect(api.ask('S-0142', { question: 'hello', lang: 'en' })).rejects.toMatchObject({ status: 404, code: 'not_found' })
  })
})

describe('POST /api/voice/stt', () => {
  it('finds the amount in a browser transcript and labels it SIMULATED', async () => {
    const api = await setup()
    const stt = await api.voiceStt({ merchant_id: 'S-0142', transcript: 'डेढ़ हज़ार रुपये कब मिलेंगे', source: 'browser', language_code: 'hi-IN' })
    expect(stt).toMatchObject({ stt_id: 'ST-000001', provider: 'browser', mode: 'SIMULATED', language_code: 'hi-IN' })
    expect(stt.mentions).toEqual([expect.objectContaining({ id: 'm1', kind: 'amount', value: '₹1,500', value_paise: 150000 })])
  })

  it('hears the scenario sample in a recording and checks the audio by its first bytes', async () => {
    const api = await setup()
    const stt = await api.voiceStt({ merchant_id: 'S-0142', file: new Blob([OGG], { type: 'audio/ogg' }), filename: 'voice.ogg' })
    expect(stt).toMatchObject({ provider: 'mock', fallback_reason: 'MOCK_BACKEND', language_code: 'hi-IN' })
    expect(stt.transcript.length).toBeGreaterThan(0)
    await expect(api.voiceStt({ merchant_id: 'S-0142', file: new Blob([new Uint8Array(16)]), filename: 'x.bin' })).rejects.toMatchObject({ status: 415 })
  })

  it('is not found while n4_voice is off', async () => {
    vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri')
    const api = await setup()
    await expect(api.voiceStt({ merchant_id: 'S-0142', transcript: 'hello', source: 'browser', language_code: 'en-IN' })).rejects.toMatchObject({ status: 404 })
  })
})

describe('a voice question', () => {
  const said = 'डेढ़ हज़ार रुपये कब मिलेंगे'
  const spoken = { merchant_id: 'S-0142', transcript: said, source: 'browser', language_code: 'hi-IN' } as const

  it('is refused with 409 until every chip of its text is confirmed', async () => {
    const api = await setup()
    const stt = await api.voiceStt(spoken)
    await expect(api.ask('S-0142', { question: said, lang: 'hi', stt_id: stt.stt_id })).rejects.toMatchObject({ status: 409, code: 'mentions_unconfirmed', fields: { mentions: 'm1' } })
    const answer = await api.ask('S-0142', { question: said, lang: 'hi', stt_id: stt.stt_id, confirmed_mentions: ['m1'] })
    expect(answer.ask_id).toMatch(/^AQ-/)
  })

  it('needs a chip for an amount that was added by editing the text', async () => {
    const api = await setup()
    const stt = await api.voiceStt(spoken)
    await expect(api.ask('S-0142', { question: `${said} 2000`, lang: 'hi', stt_id: stt.stt_id, confirmed_mentions: ['m1'] })).rejects.toMatchObject({ status: 409, fields: { mentions: 'm2' } })
  })

  it('refuses an unknown transcript id', async () => {
    const api = await setup()
    await expect(api.ask('S-0142', { question: 'hello', lang: 'en', stt_id: 'ST-000099' })).rejects.toMatchObject({ status: 404 })
  })
})

describe('POST /api/voice/tts', () => {
  it('voices only the answer of an earlier ask of the same merchant', async () => {
    const api = await setup()
    const answer = await api.ask('S-0142', { question: 'hello', lang: 'en' })
    expect(await api.voiceTts('S-0142', answer.ask_id, 'en')).toMatchObject({ audio_url: null, provider: 'browser', mode: 'SIMULATED' })
    await expect(api.voiceTts('S-0142', 'AQ-000099', 'en')).rejects.toMatchObject({ status: 404 })
    await expect(api.voiceTts('S-0907', answer.ask_id, 'en')).rejects.toMatchObject({ status: 404 })
  })
})

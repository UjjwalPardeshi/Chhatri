/** Strict parsing of the Ask Chhatri and voice bodies (data-model 5.2 and 5.11): a bad enum, a fact without a source or a label without a reason is a contract violation. */
import { describe, expect, it } from 'vitest'

import { parseAskAnswer, parseStt, parseTts } from './ask'
import { ContractViolation } from './parse'

const source = { kind: 'RULES', label: 'Payout rules, pilot-0.1', ref: 'rules:pilot-0.1:payout_share', as_of: null, origin: 'CONFIG', clause: 'C4.1' }
const answer = {
  ask_id: 'AQ-000001',
  intent: 'WHY_AMOUNT',
  intent_source: 'rules',
  lang: 'hi',
  answer: 'आपका आम मंगलवार: ₹4,380।',
  answer_en: 'Your usual Tuesday: ₹4,380.',
  clauses: [{ id: 'C4.1', title: 'Payout formula' }],
  facts_used: [{ key: 'rules.payout_share', label_hi: 'हिस्सा', label_en: 'Share', value: '50%', sources: [source] }],
  next_action: { kind: 'SEE_CLAIM', label_hi: 'मेरा दावा देखें', label_en: 'See my claim' },
  handoff: false,
  case_id: null,
  scam_warning: false,
  mode: 'LIVE',
  provider: 'rules',
  model: null,
  fallback_reason: null,
  attempts: [],
}
const stt = {
  stt_id: 'ST-000001',
  transcript: 'डेढ़ हज़ार रुपये कब मिलेंगे',
  language_code: 'hi-IN',
  language_probability: null,
  duration_s: null,
  mentions: [{ id: 'm1', kind: 'amount', heard: 'डेढ़ हज़ार', value: '₹1,500', value_paise: 150000, value_date: null, chip_hi: '₹1,500 — सही है?', chip_en: '₹1,500 — is that right?' }],
  mode: 'SIMULATED',
  provider: 'browser',
  model: null,
  fallback_reason: 'NO_KEY',
  attempts: [],
}

describe('parseAskAnswer', () => {
  it('reads the example of data-model 5.2', () => {
    const parsed = parseAskAnswer(answer)
    expect(parsed.clauses[0]).toEqual({ id: 'C4.1', title: 'Payout formula' })
    expect(parsed.next_action.kind).toBe('SEE_CLAIM')
    expect(parsed.provider).toBe('rules')
  })

  it('reads a FALLBACK answer with its attempts', () => {
    const parsed = parseAskAnswer({ ...answer, mode: 'FALLBACK', provider: 'sarvam', model: 'sarvam-105b', fallback_reason: 'TIMEOUT', attempts: [{ provider: 'gemini', outcome: 'TIMEOUT', ms: 3004 }, { provider: 'sarvam', outcome: 'OK', ms: 1210 }] })
    expect(parsed.attempts).toHaveLength(2)
    expect(parsed.fallback_reason).toBe('TIMEOUT')
  })

  it.each([
    ['an unknown mode', { mode: 'MAYBE' }],
    ['an unknown provider', { provider: 'openai' }],
    ['a next action outside the closed list', { next_action: { kind: 'SELL_LOAN', label_hi: 'x', label_en: 'x' } }],
    ['a clause id that is not in the table', { clauses: [{ id: 'C13', title: 'x' }] }],
    ['a fact with no source', { facts_used: [{ key: 'k', label_hi: 'a', label_en: 'a', value: '1', sources: [] }] }],
    ['a SIMULATED label with no reason', { mode: 'SIMULATED', fallback_reason: null }],
    ['a bad ask id', { ask_id: 'AQ-1' }],
    ['a missing scam flag', { scam_warning: undefined }],
  ])('refuses %s', (_name, patch) => {
    expect(() => parseAskAnswer({ ...answer, ...patch })).toThrow(ContractViolation)
  })

  it('refuses a body that is not an object', () => {
    expect(() => parseAskAnswer(null)).toThrow(ContractViolation)
    expect(() => parseAskAnswer([])).toThrow(ContractViolation)
  })

  it('ignores a field it does not read', () => {
    expect(parseAskAnswer({ ...answer, intent_source: 'rules', extra: 1 }).ask_id).toBe('AQ-000001')
  })
})

describe('parseStt', () => {
  it('reads the example of data-model 5.11', () => {
    const parsed = parseStt(stt)
    expect(parsed.mentions[0]).toMatchObject({ kind: 'amount', value_paise: 150000, value_date: null })
  })

  it('keeps a mention with no value, so the screen asks for the number', () => {
    const parsed = parseStt({ ...stt, mentions: [{ ...stt.mentions[0], value: null, value_paise: null }] })
    expect(parsed.mentions[0].value).toBeNull()
  })

  it.each([
    ['a duplicate mention id', { mentions: [stt.mentions[0], stt.mentions[0]] }],
    ['a mention kind that is not amount or date', { mentions: [{ ...stt.mentions[0], kind: 'name' }] }],
    ['fractional paise', { mentions: [{ ...stt.mentions[0], value_paise: 1.5 }] }],
    ['paise with no value', { mentions: [{ ...stt.mentions[0], value: null }] }],
    ['a bad stt id', { stt_id: 'ST-1' }],
  ])('refuses %s', (_name, patch) => {
    expect(() => parseStt({ ...stt, ...patch })).toThrow(ContractViolation)
  })
})

describe('parseTts', () => {
  const tts = { audio_url: null, mime_type: null, mode: 'SIMULATED', provider: 'browser', model: null, fallback_reason: 'NO_KEY' }

  it('reads a null audio url as "speak it in the browser"', () => {
    expect(parseTts(tts).audio_url).toBeNull()
  })

  it('reads a media url with its type', () => {
    expect(parseTts({ ...tts, audio_url: '/api/media/M-1', mime_type: 'audio/wav', mode: 'LIVE', provider: 'sarvam', fallback_reason: null }).mime_type).toBe('audio/wav')
  })

  it('refuses audio from outside the media route, or with no type', () => {
    expect(() => parseTts({ ...tts, audio_url: 'https://example.com/a.wav', mime_type: 'audio/wav' })).toThrow(ContractViolation)
    expect(() => parseTts({ ...tts, audio_url: '/api/media/M-1' })).toThrow(ContractViolation)
  })
})

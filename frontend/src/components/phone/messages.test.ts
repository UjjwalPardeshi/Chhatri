/** Phone thread helpers (SPEC §13). */
import { describe, expect, it } from 'vitest'

import type { Message } from '../../api/types'
import { chatMessages, latestSoundbox, spokenText, upsertMessage, voiceAudioUrl, voiceSeconds, voiceSourceLabel } from './messages'
import { pickMimeType } from './useRecorder'

function msg(id: string, at: string, extra: Partial<Message> = {}): Message {
  return {
    id,
    merchant_id: 'S-0142',
    direction: 'OUTBOUND',
    channel: 'WHATSAPP',
    kind: 'TEXT',
    text_hi: null,
    text_en: null,
    audio_url: null,
    media_url: null,
    card: null,
    created_at: at,
    meta: {},
    ...extra,
  } as Message
}

describe('phone messages', () => {
  it('upserts by id in time order, with numeric id tie-breaks', () => {
    const a = msg('M-2', '2025-08-19T17:04:00+05:30')
    const b = msg('M-10', '2025-08-19T17:04:00+05:30')
    const c = msg('M-1', '2025-08-19T17:00:00+05:30')
    const list = [a, b, c].reduce<Message[]>(upsertMessage, [])
    expect(list.map((m) => m.id)).toEqual(['M-1', 'M-2', 'M-10'])
    const edited = upsertMessage(list, { ...a, text_en: 'edited' })
    expect(edited).toHaveLength(3)
    expect(edited[1].text_en).toBe('edited')
  })

  it('separates Soundbox lines from the chat', () => {
    const box = msg('M-3', '2025-08-19T17:04:00+05:30', { channel: 'SOUNDBOX', kind: 'SOUNDBOX' })
    const chat = msg('M-4', '2025-08-19T17:05:00+05:30')
    expect(chatMessages([box, chat])).toEqual([chat])
    expect(latestSoundbox([box, chat])).toBe(box)
    expect(latestSoundbox([chat])).toBeNull()
  })

  it('estimates voice length and picks the spoken language', () => {
    expect(voiceSeconds(msg('M', '', { meta: { duration_s: 7 } }))).toBe(7)
    expect(voiceSeconds(msg('M', '', { meta: { transcript: 'x'.repeat(60) } }))).toBe(5)
    expect(voiceSeconds(msg('M', '', { text_en: 'hi' }))).toBe(2)
    expect(voiceSeconds(msg('M', ''))).toBe(2)
    expect(spokenText(msg('M', '', { text_hi: 'नमस्ते', text_en: 'Hello' }))).toEqual({ text: 'नमस्ते', lang: 'hi-IN' })
    expect(spokenText(msg('M', '', { meta: { transcript: 'बुखार' } }))).toEqual({ text: 'बुखार', lang: 'hi-IN' })
    expect(spokenText(msg('M', '', { text_en: 'Hello' }))).toEqual({ text: 'Hello', lang: 'en-IN' })
    expect(spokenText(msg('M', ''))).toEqual({ text: '', lang: 'en-IN' })
  })

  it('never plays or labels a browser-simulated clip as Sarvam audio (SPEC §0.1, §20 "Sound")', () => {
    const canned = msg('M', '', { kind: 'VOICE', audio_url: '/api/media/MD-000001', meta: { voice_source: 'browser-simulated', transcript: 'बुखार' } })
    expect(voiceAudioUrl(canned)).toBeNull()
    expect(voiceSourceLabel(canned)).toBe('browser voice')
    const bulbul = msg('M', '', { audio_url: '/api/media/MD-000002', meta: { voice_source: 'sarvam' } })
    expect(voiceAudioUrl(bulbul)).toBe('/api/media/MD-000002')
    expect(voiceSourceLabel(bulbul)).toBe('Sarvam voice')
    const recorded = msg('M', '', { kind: 'VOICE', direction: 'INBOUND', audio_url: '/api/media/MD-000003' })
    expect(voiceAudioUrl(recorded)).toBe('/api/media/MD-000003')
    expect(voiceSourceLabel(recorded)).toBe('recording')
    expect(voiceAudioUrl(msg('M', ''))).toBeNull()
    expect(voiceSourceLabel(msg('M', ''))).toBe('browser voice')
  })

  it('picks the first supported recording type', () => {
    expect(pickMimeType((t) => t === 'audio/webm')).toBe('audio/webm')
    expect(pickMimeType(() => false)).toBe('')
  })
})

/** Phone thread helpers (SPEC §13). */
import { describe, expect, it } from 'vitest'

import type { Message } from '../../api/types'
import { chatMessages, latestSoundbox, spokenText, upsertMessage, voiceSeconds } from './messages'
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

  it('picks the first supported recording type', () => {
    expect(pickMimeType((t) => t === 'audio/webm')).toBe('audio/webm')
    expect(pickMimeType(() => false)).toBe('')
  })
})

/** Pure helpers for the phone thread (ordering, upserts, voice durations). */
import type { Message } from '../../api/types'

const CHARS_PER_SECOND = 12
const MIN_VOICE_SECONDS = 2

export function compareMessages(a: Message, b: Message): number {
  return Date.parse(a.created_at) - Date.parse(b.created_at) || a.id.localeCompare(b.id, 'en', { numeric: true })
}

/** Inserts or replaces by id, keeping chronological order; returns a new array. */
export function upsertMessage(list: readonly Message[], message: Message): Message[] {
  const without = list.filter((m) => m.id !== message.id)
  return [...without, message].toSorted(compareMessages)
}

export function chatMessages(list: readonly Message[]): Message[] {
  return list.filter((m) => m.channel !== 'SOUNDBOX' && m.kind !== 'SOUNDBOX')
}

export function latestSoundbox(list: readonly Message[]): Message | null {
  return list.filter((m) => m.channel === 'SOUNDBOX' || m.kind === 'SOUNDBOX').at(-1) ?? null
}

export function voiceSeconds(message: Message): number {
  if (message.meta.duration_s !== undefined) return message.meta.duration_s
  const text = message.meta.transcript ?? message.text_hi ?? message.text_en ?? ''
  return Math.max(MIN_VOICE_SECONDS, Math.round(text.length / CHARS_PER_SECOND))
}

/** Text to speak for a bubble: Hindi first (Bulbul speaks the Hindi line, SPEC §13.1). */
export function spokenText(message: Message): { text: string; lang: 'hi-IN' | 'en-IN' } {
  const hindi = message.text_hi ?? message.meta.transcript
  if (hindi) return { text: hindi, lang: 'hi-IN' }
  return { text: message.text_en ?? '', lang: 'en-IN' }
}

/**
 * The audio to play for a bubble, or null when the console speaks it itself (SPEC §0.1, §20
 * "Sound"): `browser-simulated` notes carry only a silent WAV clip (the canned deck voice notes), so
 * playing that clip would be silent, and calling it Sarvam would present a simulation as live.
 */
export function voiceAudioUrl(message: Message): string | null {
  return message.meta.voice_source === 'browser-simulated' ? null : message.audio_url
}

export type VoiceSourceLabel = 'Sarvam voice' | 'recording' | 'browser voice'

/** Who speaks a voice bubble: Sarvam Bulbul audio, the merchant's own recording, or the browser (hi-IN). */
export function voiceSourceLabel(message: Message): VoiceSourceLabel {
  if (!voiceAudioUrl(message)) return 'browser voice'
  return message.direction === 'OUTBOUND' && message.meta.voice_source === 'sarvam' ? 'Sarvam voice' : 'recording'
}

/** Sound gating (SPEC §20 "Sound"): auto-play only after "Enable sound"; taps always play. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ENGLISH_LANG, HINDI_LANG, SoundManager } from './sound'

class FakeUtterance {
  text: string
  lang = ''
  rate = 1
  voice: unknown = null
  constructor(text: string) {
    this.text = text
  }
}

const synth = { speak: vi.fn<(u: FakeUtterance) => void>(), cancel: vi.fn<() => void>(), getVoices: () => [{ lang: HINDI_LANG, name: 'hi' }] }

beforeEach(() => {
  synth.speak.mockReset()
  synth.cancel.mockReset()
  vi.stubGlobal('speechSynthesis', synth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
})
afterEach(() => vi.unstubAllGlobals())

describe('SoundManager', () => {
  it('speaks Hindi with the hi-IN voice at the demo rate', () => {
    const sound = new SoundManager()
    expect(sound.speak('नमस्ते')).toBe('speech')
    const utterance = synth.speak.mock.calls[0][0] as FakeUtterance
    expect(utterance).toMatchObject({ text: 'नमस्ते', lang: HINDI_LANG, rate: 0.95 })
    expect(utterance.voice).toEqual({ lang: HINDI_LANG, name: 'hi' })
    expect(sound.speak('hello', ENGLISH_LANG)).toBe('speech')
    expect((synth.speak.mock.calls[1][0] as FakeUtterance).voice).toBeNull()
    expect(sound.speak('   ')).toBe('unavailable')
  })

  it('only auto-plays after enabling, and notifies subscribers', async () => {
    const sound = new SoundManager()
    const seen: boolean[] = []
    const off = sound.subscribe((on) => seen.push(on))
    expect(await sound.autoPlay('x', null)).toBe('unavailable')
    sound.setEnabled(true)
    expect(sound.isEnabled()).toBe(true)
    expect(await sound.autoPlay('x', null)).toBe('speech')
    sound.setEnabled(false)
    expect(synth.cancel).toHaveBeenCalled()
    off()
    sound.setEnabled(true)
    expect(seen).toEqual([true, false])
  })

  it('plays real audio when given and falls back to speech when playback fails', async () => {
    const play = vi.fn<() => Promise<void>>().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('blocked'))
    vi.stubGlobal('Audio', function Audio() {
      return { play }
    })
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const sound = new SoundManager()
    expect(await sound.play('x', '/api/media/a.wav')).toBe('audio')
    expect(await sound.play('x', '/api/media/a.wav')).toBe('speech')
  })

  it('reports unavailable without speechSynthesis', () => {
    vi.unstubAllGlobals()
    vi.stubGlobal('SpeechSynthesisUtterance', undefined)
    expect(SoundManager.speechAvailable()).toBe(false)
    const sound = new SoundManager()
    expect(sound.speak('x')).toBe('unavailable')
    sound.stop()
  })
})

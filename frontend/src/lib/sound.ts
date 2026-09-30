/**
 * Sound for the demo (SPEC §20 "Sound"): browsers block autoplay, so nothing plays until the
 * presenter presses "Enable sound" (a user gesture). Real audio (`audio_url`, Sarvam Bulbul) plays
 * when present; otherwise the browser's speechSynthesis speaks Hindi (hi-IN), labelled in the UI.
 */

export const HINDI_LANG = 'hi-IN'
export const ENGLISH_LANG = 'en-IN'
const SPEECH_RATE = 0.95

export type SpeakResult = 'audio' | 'speech' | 'unavailable'

export class SoundManager {
  private enabled = false
  private listeners = new Set<(enabled: boolean) => void>()

  isEnabled(): boolean {
    return this.enabled
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled
    if (!enabled) this.stop()
    for (const listener of this.listeners) listener(enabled)
  }

  subscribe(listener: (enabled: boolean) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  static speechAvailable(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'
  }

  /** Plays `audioUrl` when given, else speaks `text`. Explicit taps play even when auto-play is off. */
  async play(text: string, audioUrl: string | null, lang = HINDI_LANG): Promise<SpeakResult> {
    if (audioUrl) {
      try {
        await new Audio(audioUrl).play()
        return 'audio'
      } catch (error) {
        console.warn('[sound] audio playback failed; using browser speech', error)
      }
    }
    return this.speak(text, lang)
  }

  /** Auto-play entry point (Soundbox, incoming voice notes): only after "Enable sound". */
  async autoPlay(text: string, audioUrl: string | null, lang = HINDI_LANG): Promise<SpeakResult> {
    if (!this.enabled) return 'unavailable'
    return this.play(text, audioUrl, lang)
  }

  speak(text: string, lang = HINDI_LANG): SpeakResult {
    if (!SoundManager.speechAvailable() || text.trim() === '') return 'unavailable'
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = SPEECH_RATE
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang === lang)
    if (voice) utterance.voice = voice
    window.speechSynthesis.speak(utterance)
    return 'speech'
  }

  stop(): void {
    if (SoundManager.speechAvailable()) window.speechSynthesis.cancel()
  }
}

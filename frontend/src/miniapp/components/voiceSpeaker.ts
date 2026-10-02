/**
 * Playing an answer aloud (fs-05 section 11.3, `POST /api/voice/tts`). Only the answer of an earlier ask can be voiced.
 * The reply is audio from the media route (Sarvam, demo merchants only) or `audio_url` null, which means the browser
 * speaks the text itself with `speechSynthesis`. When neither works the answer stays on screen as text, which it
 * always does. The label of the speaker (mode and provider) is returned so the screen can show it while it is not LIVE.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { useLive } from '../../state/live'
import type { AiLabel, AskAnswer } from '../api/ask'

export type SpeakerState = 'idle' | 'loading' | 'speaking' | 'unavailable'

export type SpeakerDeps = {
  createAudio?: (url: string) => HTMLAudioElement
  synth?: SpeechSynthesis | null
  utterance?: (text: string) => SpeechSynthesisUtterance
}

const SPEECH_LANG = { hi: 'hi-IN', en: 'en-IN' } as const

function defaultSynth(): SpeechSynthesis | null {
  return typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null
}

export function useSpeaker(merchantId: string, deps: SpeakerDeps = {}) {
  const { api } = useLive()
  const [state, setState] = useState<SpeakerState>('idle')
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const [label, setLabel] = useState<AiLabel | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const run = useRef(0)
  const synth = deps.synth === undefined ? defaultSynth() : deps.synth

  const halt = useCallback(() => {
    run.current += 1
    audio.current?.pause()
    audio.current = null
    synth?.cancel()
    setState('idle')
    setSpeakingId(null)
  }, [synth])

  const speak = useCallback(
    async (answer: AskAnswer) => {
      halt()
      const token = run.current
      setSpeakingId(answer.ask_id)
      setState('loading')
      const done = (): void => {
        if (token !== run.current) return
        setState('idle')
        setSpeakingId(null)
      }
      try {
        const tts = await api.voiceTts(merchantId, answer.ask_id, answer.lang)
        if (token !== run.current) return
        setLabel({ mode: tts.mode, provider: tts.provider, model: tts.model, fallback_reason: tts.fallback_reason })
        if (tts.audio_url !== null) {
          const element = (deps.createAudio ?? ((url: string) => new Audio(url)))(api.client.url(tts.audio_url))
          audio.current = element
          element.addEventListener('ended', done, { once: true })
          element.addEventListener('error', done, { once: true })
          setState('speaking')
          await element.play()
          return
        }
        if (synth === null) {
          setState('unavailable')
          setSpeakingId(null)
          return
        }
        const utterance = (deps.utterance ?? ((text: string) => new SpeechSynthesisUtterance(text)))(answer.answer)
        utterance.lang = SPEECH_LANG[answer.lang]
        utterance.addEventListener('end', done, { once: true })
        utterance.addEventListener('error', done, { once: true })
        setState('speaking')
        synth.speak(utterance)
      } catch {
        if (token !== run.current) return
        setState('unavailable')
        setSpeakingId(null)
      }
    },
    [api, deps, halt, merchantId, synth],
  )

  useEffect(() => halt, [halt])

  return { state, speakingId, label, speak, stop: halt }
}

export type Speaker = ReturnType<typeof useSpeaker>

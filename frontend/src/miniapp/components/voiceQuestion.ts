/**
 * The voice half of the Ask composer (fs-05 section 11, screens 5.4): the mic, the transcript that fills the text box,
 * and the chips that must be confirmed before Send works. Voice never sends on its own. It runs the states of the
 * screen design: idle, notice (once), listening with a timer that stops itself at 30 seconds, processing, heard
 * nothing, error and unavailable. Editing the text reads it again (`POST /api/voice/stt` with the words), so an amount
 * added by hand gets its own chip, and a confirmation survives edits of the words around it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useLatest } from '../../state/useLatest'
import { useLive } from '../../state/live'
import { VOICE_MAX_SECONDS, type AiLabel, type Mention, type SttResult } from '../api/ask'
import { allConfirmed, confirmedIds, mentionKey, pendingMentions, type KalChoice } from './voiceMentions'
import { detectVoiceEngine, VoiceFailure, type VoiceCapture, type VoiceEngine, type VoiceSession } from './voiceEngine'

export type VoicePhase = 'idle' | 'notice' | 'listening' | 'processing' | 'unclear' | 'error'
export type VoiceErrorCode = 'denied' | 'unsupported' | 'failed'

export const NOTICE_STORAGE_KEY = 'chhatri.miniapp.voice_notice_seen'
const REREAD_DELAY_MS = 400

function noticeSeen(): boolean {
  try {
    return window.localStorage.getItem(NOTICE_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function rememberNotice(): void {
  try {
    window.localStorage.setItem(NOTICE_STORAGE_KEY, '1')
  } catch {
    // Storage is blocked: the notice shows again next time, which is harmless.
  }
}

type Transcript = { id: string; label: AiLabel; mentions: Mention[] }

export type VoiceQuestionArgs = {
  merchantId: string
  lang: 'hi' | 'en'
  text: string
  setText: (text: string) => void
  /** Tests give a fake; the screen leaves it out and the browser's own engine is used. */
  engine?: VoiceEngine | null
}

export function useVoiceQuestion({ merchantId, lang, text, setText, engine }: VoiceQuestionArgs) {
  const { api } = useLive()
  const chosen = useMemo(() => (engine === undefined ? detectVoiceEngine(lang) : engine), [engine, lang])
  const [phase, setPhase] = useState<VoicePhase>('idle')
  const [seconds, setSeconds] = useState(0)
  const [errorCode, setErrorCode] = useState<VoiceErrorCode | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [confirmed, setConfirmed] = useState<ReadonlySet<string>>(new Set())
  const [checking, setChecking] = useState(false)
  const session = useRef<VoiceSession | null>(null)
  const ticker = useRef<ReturnType<typeof setInterval> | null>(null)
  const run = useRef(0)
  const reread = useRef(0)
  const elapsed = useRef(0)
  const analysed = useRef('')
  const languageCode = lang === 'hi' ? 'hi-IN' : 'en-IN'
  const setTextLatest = useLatest(setText)

  const clearTicker = useCallback(() => {
    if (ticker.current !== null) clearInterval(ticker.current)
    ticker.current = null
  }, [])

  const adopt = useCallback(
    (result: SttResult, keep: ReadonlySet<string>) => {
      const { stt_id: id, mentions, mode, provider, model, fallback_reason } = result
      setTranscript({ id, mentions, label: { mode, provider, model, fallback_reason } })
      setConfirmed(keep)
    },
    [],
  )

  const finish = useCallback(
    async (capture: VoiceCapture, token: number) => {
      setPhase('processing')
      try {
        const result =
          capture.kind === 'transcript'
            ? capture.transcript.trim() === ''
              ? null
              : await api.voiceStt({ merchant_id: merchantId, transcript: capture.transcript, source: 'browser', language_code: capture.languageCode })
            : await api.voiceStt({ merchant_id: merchantId, file: capture.blob, filename: capture.filename, lang_hint: languageCode })
        if (token !== run.current) return
        if (result === null || result.transcript.trim() === '') {
          setPhase('unclear')
          return
        }
        analysed.current = result.transcript
        setTextLatest.current(result.transcript)
        adopt(result, new Set())
        setPhase('idle')
      } catch {
        if (token !== run.current) return
        setErrorCode('failed')
        setPhase('error')
      }
    },
    [adopt, api, languageCode, merchantId, setTextLatest],
  )

  const begin = useCallback(async () => {
    if (chosen === null) return
    const token = ++run.current
    setErrorCode(null)
    try {
      const started = await chosen.start()
      if (token !== run.current) {
        started.cancel()
        return
      }
      session.current = started
      setSeconds(0)
      setPhase('listening')
      elapsed.current = 0
      ticker.current = setInterval(() => {
        elapsed.current += 1
        setSeconds(elapsed.current)
        if (elapsed.current >= VOICE_MAX_SECONDS) {
          setPhase('processing')
          started.stop()
        }
      }, 1000)
      started.result
        .then((capture) => {
          clearTicker()
          if (token === run.current) void finish(capture, token)
        })
        .catch((error: unknown) => {
          clearTicker()
          if (token !== run.current) return
          setErrorCode(error instanceof VoiceFailure ? error.code : 'failed')
          setPhase('error')
        })
    } catch (error) {
      if (token !== run.current) return
      setErrorCode(error instanceof VoiceFailure ? error.code : 'failed')
      setPhase('error')
    }
  }, [chosen, clearTicker, finish])

  const start = useCallback(() => {
    if (!noticeSeen() && phase !== 'notice') {
      setPhase('notice')
      return
    }
    void begin()
  }, [begin, phase])

  const acceptNotice = useCallback(() => {
    rememberNotice()
    void begin()
  }, [begin])

  const stop = useCallback(() => {
    setPhase('processing')
    session.current?.stop()
  }, [])

  const cancel = useCallback(() => {
    run.current += 1
    clearTicker()
    session.current?.cancel()
    session.current = null
    setPhase('idle')
  }, [clearTicker])

  const reset = useCallback(() => {
    setTranscript(null)
    setConfirmed(new Set())
    setChecking(false)
    analysed.current = ''
  }, [])

  const confirm = useCallback((mention: Mention, choice?: KalChoice) => setConfirmed((prev) => new Set([...prev, mentionKey(mention, choice)])), [])

  /** Reads edited words again, so an amount typed by hand gets a chip and an emptied box clears them. */
  useEffect(() => {
    if (transcript === null || text === analysed.current || text.trim() === '') return undefined
    setChecking(true)
    const timer = setTimeout(() => {
      const token = ++reread.current
      api
        .voiceStt({ merchant_id: merchantId, transcript: text, source: 'browser', language_code: languageCode })
        .then((result) => {
          if (token !== reread.current) return
          analysed.current = text
          adopt(result, confirmed)
          setChecking(false)
        })
        .catch(() => {
          if (token === reread.current) setChecking(false)
        })
    }, REREAD_DELAY_MS)
    return () => clearTimeout(timer)
  }, [adopt, api, confirmed, languageCode, merchantId, text, transcript])

  useEffect(
    () => () => {
      run.current += 1
      if (ticker.current !== null) clearInterval(ticker.current)
      session.current?.cancel()
    },
    [],
  )

  /** An emptied box has no chips: its words are gone, so nothing is left to confirm. */
  const active = transcript !== null && text.trim() !== ''
  const mentions = active ? transcript.mentions : []
  return {
    available: chosen !== null,
    phase,
    seconds,
    maxSeconds: VOICE_MAX_SECONDS,
    errorCode,
    transcript: active ? transcript : null,
    mentions,
    pending: pendingMentions(mentions, confirmed),
    confirmed,
    confirmedIds: confirmedIds(mentions, confirmed),
    checking,
    /** A voice question can go when every chip is confirmed and the words have been read again. */
    ready: !active || (allConfirmed(mentions, confirmed) && !checking),
    sttId: active ? transcript.id : null,
    start,
    acceptNotice,
    stop,
    cancel,
    confirm,
    reset,
  }
}

export type VoiceQuestion = ReturnType<typeof useVoiceQuestion>

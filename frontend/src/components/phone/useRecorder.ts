/**
 * Microphone recording for voice notes (SPEC §19 POST /voice: audio ≤ 5 MB and ≤ 30 s).
 * MediaRecorder → one Blob; stops itself at the 30-second limit.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { useLatest } from '../../state/useLatest'

export const MAX_RECORD_SECONDS = 30
const PREFERRED_TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm']
const SECOND_MS = 1_000

export type RecorderState = { status: 'idle' | 'recording' | 'error'; seconds: number; error: string | null }

export function pickMimeType(isSupported: (type: string) => boolean): string {
  return PREFERRED_TYPES.find((type) => isSupported(type)) ?? ''
}

export function useRecorder(onDone: (blob: Blob, filename: string) => void) {
  const [state, setState] = useState<RecorderState>({ status: 'idle', seconds: 0, error: null })
  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const doneRef = useLatest(onDone)

  const cleanup = useCallback(() => {
    if (timer.current) clearInterval(timer.current)
    timer.current = null
    recorder.current?.stream.getTracks().forEach((track) => track.stop())
    recorder.current = null
  }, [])

  const stop = useCallback(() => {
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }, [])

  const start = useCallback(async () => {
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setState({ status: 'error', seconds: 0, error: 'This browser cannot record audio' })
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = pickMimeType((type) => MediaRecorder.isTypeSupported(type))
      const media = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      const chunks: Blob[] = []
      media.ondataavailable = (event) => chunks.push(event.data)
      media.onstop = () => {
        const type = media.mimeType || 'audio/webm'
        cleanup()
        setState({ status: 'idle', seconds: 0, error: null })
        doneRef.current(new Blob(chunks, { type }), type.includes('ogg') ? 'voice-note.ogg' : 'voice-note.webm')
      }
      recorder.current = media
      media.start()
      setState({ status: 'recording', seconds: 0, error: null })
      timer.current = setInterval(() => {
        setState((s) => {
          const seconds = s.seconds + 1
          if (seconds >= MAX_RECORD_SECONDS) stop()
          return { ...s, seconds }
        })
      }, SECOND_MS)
    } catch (error) {
      console.warn('[recorder] microphone unavailable', error)
      cleanup()
      setState({ status: 'error', seconds: 0, error: 'Microphone permission denied or unavailable' })
    }
  }, [cleanup, stop, doneRef])

  useEffect(() => cleanup, [cleanup])
  return { state, start, stop }
}

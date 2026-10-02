/**
 * The two ways the browser can hear the merchant (fs-05 section 11): the browser's own speech recognition, which gives
 * words and sends no audio to the server, and the recorder, which gives audio for `POST /api/voice/stt`. A session is
 * one capture: `result` settles when it ends (the merchant stopped it, the limit came, or the browser heard enough),
 * `stop()` ends it and `cancel()` throws it away. Nothing is stored. A device with neither gives `null`, and the mic
 * is not drawn (state "Not available"). Everything touching the window is injectable, so the tests need no microphone.
 */
export type VoiceCapture =
  | { kind: 'transcript'; transcript: string; languageCode: string }
  | { kind: 'audio'; blob: Blob; filename: string }

export type VoiceFailureCode = 'denied' | 'unsupported'

export class VoiceFailure extends Error {
  readonly code: VoiceFailureCode
  constructor(code: VoiceFailureCode, message: string) {
    super(message)
    this.name = 'VoiceFailure'
    this.code = code
  }
}

export type VoiceSession = { result: Promise<VoiceCapture>; stop: () => void; cancel: () => void }
export type VoiceEngine = { kind: 'browser' | 'recorder'; start: () => Promise<VoiceSession> }

type RecognitionResultEvent = Event & { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }> }
type Recognition = {
  lang: string
  continuous: boolean
  interimResults: boolean
  addEventListener: {
    (type: 'result', listener: (event: RecognitionResultEvent) => void): void
    (type: 'error', listener: (event: Event & { error?: string }) => void): void
    (type: 'end', listener: () => void): void
  }
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionConstructor = new () => Recognition
export type SpeechWindow = Window & {
  MediaRecorder?: typeof MediaRecorder
  SpeechRecognition?: RecognitionConstructor
  webkitSpeechRecognition?: RecognitionConstructor
}

const LANGUAGE_CODE = { hi: 'hi-IN', en: 'en-IN' } as const
const DENIED_ERRORS: ReadonlySet<string> = new Set(['not-allowed', 'service-not-allowed'])

function browserEngine(Recognizer: RecognitionConstructor, lang: 'hi' | 'en'): VoiceEngine {
  const languageCode = LANGUAGE_CODE[lang]
  return {
    kind: 'browser',
    start: () => {
      const recognition = new Recognizer()
      recognition.lang = languageCode
      recognition.continuous = false
      recognition.interimResults = false
      let heard = ''
      let cancelled = false
      const result = new Promise<VoiceCapture>((resolve, reject) => {
        recognition.addEventListener('result', (event) => {
          heard = Array.from(event.results, (r) => r[0]?.transcript ?? '').join(' ').trim()
        })
        recognition.addEventListener('error', (event) => {
          if (event.error !== undefined && DENIED_ERRORS.has(event.error)) reject(new VoiceFailure('denied', event.error))
        })
        recognition.addEventListener('end', () => {
          if (!cancelled) resolve({ kind: 'transcript', transcript: heard, languageCode })
        })
      })
      result.catch(() => undefined)
      recognition.start()
      return Promise.resolve({
        result,
        stop: () => recognition.stop(),
        cancel: () => {
          cancelled = true
          recognition.abort()
        },
      })
    },
  }
}

const RECORDER_TYPES = [
  { mime: 'audio/webm;codecs=opus', file: 'voice.webm' },
  { mime: 'audio/ogg;codecs=opus', file: 'voice.ogg' },
  { mime: 'audio/mp4', file: 'voice.m4a' },
] as const

function recorderEngine(): VoiceEngine {
  return {
    kind: 'recorder',
    start: async () => {
      let stream: MediaStream
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch {
        throw new VoiceFailure('denied', 'microphone permission denied')
      }
      const chosen = RECORDER_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type.mime)) ?? RECORDER_TYPES[0]
      const recorder = new MediaRecorder(stream, { mimeType: chosen.mime })
      const chunks: Blob[] = []
      let cancelled = false
      const release = (): void => stream.getTracks().forEach((track) => track.stop())
      const result = new Promise<VoiceCapture>((resolve) => {
        recorder.addEventListener('dataavailable', (event) => chunks.push(event.data))
        recorder.addEventListener('stop', () => {
          release()
          if (!cancelled) resolve({ kind: 'audio', blob: new Blob(chunks, { type: chosen.mime }), filename: chosen.file })
        })
      })
      recorder.start()
      return {
        result,
        stop: () => recorder.state !== 'inactive' && recorder.stop(),
        cancel: () => {
          cancelled = true
          if (recorder.state !== 'inactive') recorder.stop()
          else release()
        },
      }
    },
  }
}

/** Browser recognition first (real words, no upload), then the recorder, else null. */
export function detectVoiceEngine(lang: 'hi' | 'en', win: SpeechWindow = window): VoiceEngine | null {
  const Recognizer = win.SpeechRecognition ?? win.webkitSpeechRecognition
  if (Recognizer) return browserEngine(Recognizer, lang)
  const hasRecorder = typeof win.MediaRecorder === 'function' && typeof win.navigator?.mediaDevices?.getUserMedia === 'function'
  return hasRecorder ? recorderEngine() : null
}

/**
 * The three calls of Ask Chhatri and voice (data-model 5.2 and 5.11), mixed into `createApi`. Input is validated
 * here, at the client boundary, so a bad id, an empty or over-long question or an oversized recording never reaches
 * the server; the answers go through the strict parsers of `ask.ts`.
 */
import { ApiError, type ApiClient } from '../../api/client'
import {
  ASK_MAX_CHARS,
  parseAskAnswer,
  parseStt,
  parseTts,
  type AskAnswer,
  type AskRequest,
  type SttRequest,
  type SttResult,
  type TtsResult,
} from './ask'

const MERCHANT_ID = /^S-\d{4}$/
const ASK_ID = /^AQ-\d{6}$/
const MAX_AUDIO_BYTES = 5 * 1024 * 1024

const invalid = (field: string, reason: string): ApiError => new ApiError('VALIDATION_ERROR', 'Invalid input', 0, { [field]: reason })

function merchant(id: string): string {
  if (!MERCHANT_ID.test(id)) throw invalid('merchant_id', 'must look like S-0142')
  return id
}

export function askCalls(client: ApiClient) {
  return {
    /** POST /api/merchants/{id}/ask. A voice question carries its `stt_id` and the ids of the chips that were confirmed. */
    ask: async (merchantId: string, request: AskRequest): Promise<AskAnswer> => {
      const question = request.question.trim()
      if (question.length === 0) throw invalid('question', 'type a question first')
      if (question.length > ASK_MAX_CHARS) throw invalid('question', `at most ${ASK_MAX_CHARS} characters`)
      const body = { ...request, question }
      return parseAskAnswer(await client.post<unknown>(`/api/merchants/${merchant(merchantId)}/ask`, body))
    },
    /** POST /api/voice/stt: a recording (multipart) or what the browser recognised (JSON, no audio leaves the device). */
    voiceStt: async (request: SttRequest): Promise<SttResult> => {
      const id = merchant(request.merchant_id)
      if ('file' in request) {
        if (request.file.size === 0) throw invalid('file', 'recording is empty')
        if (request.file.size > MAX_AUDIO_BYTES) throw invalid('file', 'recording must be 5 MB or smaller')
        const form = new FormData()
        form.append('merchant_id', id)
        form.append('file', request.file, request.filename)
        if (request.lang_hint) form.append('lang_hint', request.lang_hint)
        return parseStt(await client.postForm<unknown>('/api/voice/stt', form))
      }
      if (request.transcript.trim().length === 0) throw invalid('transcript', 'nothing was heard')
      return parseStt(await client.post<unknown>('/api/voice/stt', { ...request, merchant_id: id }))
    },
    /** POST /api/voice/tts: only the answer of an earlier ask can be voiced. */
    voiceTts: async (merchantId: string, askId: string, lang: 'hi' | 'en'): Promise<TtsResult> => {
      if (!ASK_ID.test(askId)) throw invalid('ask_id', 'must look like AQ-000001')
      return parseTts(await client.post<unknown>('/api/voice/tts', { merchant_id: merchant(merchantId), ask_id: askId, lang }))
    },
  }
}

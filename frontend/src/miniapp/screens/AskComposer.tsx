/**
 * The composer of the Ask screen (screens 5.1 and 5.4): a text box (16 px, so iOS does not zoom), a counter near the
 * 500-character limit, the mic with its states and chips when `n4_voice` is on, and Send. Send is off while the box is
 * empty or too long, while a voice question still has an unconfirmed amount or date (with the hint beside it), and
 * while the device is offline. The typed text is never cleared by a failure.
 */
import type { RefObject } from 'react'

import { ASK_MAX_CHARS } from '../api/ask'
import { VoiceButton, VoiceStatus } from '../components/voiceButton'
import { MentionChips } from '../components/voiceChips'
import type { VoiceQuestion } from '../components/voiceQuestion'
import { ta } from '../copy/ask'
import { t } from '../lib/copy'
import type { Lang } from '../lib/lang'
import { NetworkButton } from '../shell/SharedStates'
import { Textarea } from '../ui/textarea'

const COUNTER_FROM = 450

type Props = {
  lang: Lang
  text: string
  onText: (text: string) => void
  onSend: () => void
  field: RefObject<HTMLTextAreaElement | null>
  online: boolean
  sending: boolean
  /** Null while `n4_voice` is off: no mic, no chips, no notice. */
  voice: VoiceQuestion | null
}

export function AskComposer({ lang, text, onText, onSend, field, online, sending, voice }: Props) {
  const trimmed = text.trim().length
  const tooLong = trimmed > ASK_MAX_CHARS
  const holding = voice !== null && !voice.ready
  const canSend = trimmed > 0 && !tooLong && !holding && !sending
  const heard = voice !== null && voice.transcript !== null
  return (
    <form
      data-testid="ask-composer"
      className="flex flex-col gap-2 border-t bg-background p-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (canSend) onSend()
      }}
    >
      {voice === null ? null : <VoiceStatus voice={voice} lang={lang} />}
      {heard && voice !== null ? <MentionChips voice={voice} lang={lang} field={field} /> : null}
      {online ? null : <p data-testid="ask-offline" className="text-sm text-referred-ink">{ta('ASK_OFFLINE', lang)}</p>}
      <label className="flex flex-col gap-1">
        <span className={heard ? 'text-sm font-medium' : 'sr-only'}>{heard ? ta('voice.transcript.label', lang) : ta('ask.placeholder', lang)}</span>
        <Textarea
          ref={field}
          data-testid="ask-input"
          value={text}
          rows={2}
          placeholder={ta('ask.placeholder', lang)}
          aria-invalid={tooLong ? true : undefined}
          className="min-h-[3.25rem] text-field"
          onChange={(event) => onText(event.target.value)}
        />
      </label>
      {trimmed >= COUNTER_FROM ? (
        <p data-testid="ask-counter" className={tooLong ? 'num text-sm text-blocked' : 'num text-xs text-ink-3'}>
          {tooLong ? `${ta('ASK_TOO_LONG', lang)} ` : ''}
          {trimmed}/{ASK_MAX_CHARS}
        </p>
      ) : null}
      {holding ? <p data-testid="ask-send-hint" className="text-xs text-ink-2">{ta('voice.send.hint', lang)}</p> : null}
      {voice !== null && !voice.available ? <p data-testid="voice-unavailable" className="text-xs text-ink-3">{ta('voice.state.fallback', lang)}</p> : null}
      <div className="flex items-start gap-2">
        {voice !== null && voice.available ? (
          <div className="flex flex-col gap-1">
            <VoiceButton voice={voice} lang={lang} disabled={!online || sending} />
            {online ? null : <p className="max-w-40 text-xs text-ink-3">{t('offline.blocked', lang)}</p>}
          </div>
        ) : null}
        <div className="ml-auto flex flex-col items-end gap-1">
          <NetworkButton data-testid="ask-send" type="submit" size="lg" disabled={!canSend}>
            {ta('ask.btn.send', lang)}
          </NetworkButton>
        </div>
      </div>
    </form>
  )
}

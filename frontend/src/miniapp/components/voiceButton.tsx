/**
 * The mic button and the line under it (screens 5.4). The button is 44 px and says in words what a tap does: Speak
 * to start, Stop while it listens. The line follows the voice state: the notice (once), the timer, "understanding",
 * heard nothing, or the way out of an error. `VoiceStatus` is an `aria-live` region, so a screen reader hears each change.
 */
import { LoaderCircle, Mic, Square } from 'lucide-react'

import { VOICE_MAX_SECONDS } from '../api/ask'
import { ta } from '../copy/ask'
import { t } from '../lib/copy'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import type { VoiceQuestion } from './voiceQuestion'

export function VoiceButton({ voice, lang, disabled }: { voice: VoiceQuestion; lang: Lang; disabled?: boolean }) {
  const listening = voice.phase === 'listening'
  const busy = voice.phase === 'processing' || voice.phase === 'notice'
  return (
    <Button
      data-testid="voice-mic"
      data-listening={listening ? 'true' : 'false'}
      type="button"
      variant={listening ? 'default' : 'outline'}
      size="lg"
      disabled={disabled === true || busy}
      aria-label={ta(listening ? 'voice.btn.stop' : 'voice.btn.speak', lang)}
      onClick={listening ? voice.stop : voice.start}
    >
      {listening ? <Square aria-hidden="true" /> : <Mic aria-hidden="true" />}
      {ta(listening ? 'voice.btn.stop' : 'voice.btn.speak', lang)}
    </Button>
  )
}

function Notice({ voice, lang }: { voice: VoiceQuestion; lang: Lang }) {
  return (
    <div data-testid="voice-notice" className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <p className="text-sm">{ta('ASK_VOICE_NOTICE', lang)}</p>
      <div className="flex gap-2">
        <Button data-testid="voice-notice-continue" className="flex-1" onClick={voice.acceptNotice}>
          {ta('voice.btn.speak', lang)}
        </Button>
        <Button data-testid="voice-notice-cancel" variant="outline" className="flex-1" onClick={voice.cancel}>
          {ta('ask.btn.cancel', lang)}
        </Button>
      </div>
    </div>
  )
}

export function VoiceStatus({ voice, lang }: { voice: VoiceQuestion; lang: Lang }) {
  const { phase } = voice
  let body = null
  if (phase === 'notice') body = <Notice voice={voice} lang={lang} />
  else if (phase === 'listening') body = <p className="num text-sm text-ink-2">{ta('voice.state.listening', lang, { seconds: voice.seconds, max_seconds: VOICE_MAX_SECONDS })}</p>
  else if (phase === 'processing') {
    body = (
      <div className="flex items-center gap-2 text-sm text-ink-2">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        <span>{ta('voice.state.processing', lang)}</span>
        <Button data-testid="voice-cancel" variant="ghost" onClick={voice.cancel}>
          {ta('ask.btn.cancel', lang)}
        </Button>
      </div>
    )
  } else if (phase === 'unclear') body = <p className="text-sm text-referred-ink">{ta('VOICE_UNCLEAR', lang)}</p>
  else if (phase === 'error') {
    body = (
      <p className="text-sm text-blocked">
        {voice.errorCode === 'failed' ? t('error.generic', lang) : `${ta(voice.errorCode === 'unsupported' ? 'voice.err.unsupported' : 'voice.err.denied', lang)} ${ta('voice.err.fix', lang)}`}
      </p>
    )
  }
  return (
    <div data-testid="voice-status" data-phase={phase} aria-live="polite" className="empty:hidden">
      {body}
    </div>
  )
}

/**
 * The confirmation chips of a voice question (H18, screens 5.4): one chip for each amount and date in the final text,
 * with Right and Change. An amount or a date is used only after the merchant confirms it. The Hindi word कल asks which
 * day was meant, and words the parser could not read ask for the number to be typed; nothing is guessed. The words
 * are the deck's (`ASK_MENTION_CHIP`, `ASK_MENTION_WORDS`, `voice.chip.*`), not the server's proposed chip text.
 */
import { Check } from 'lucide-react'
import type { RefObject } from 'react'

import type { Mention } from '../api/ask'
import { ta } from '../copy/ask'
import { cn } from '../lib/cn'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import type { VoiceQuestion } from './voiceQuestion'
import { isConfirmed, isKal, needsTyping, type KalChoice } from './voiceMentions'

const BOX = 'flex flex-col gap-2 rounded-lg border bg-card p-3'

function Confirmed({ lang, detail }: { lang: Lang; detail?: string }) {
  return (
    <p className="flex items-center gap-1.5 text-sm font-medium text-paid-ink">
      <Check className="size-4" aria-hidden="true" />
      {ta('voice.chip.confirmed', lang)}
      {detail ? <span className="font-normal text-ink-2">· {detail}</span> : null}
    </p>
  )
}

function KalChip({ mention, voice, lang }: { mention: Mention; voice: VoiceQuestion; lang: Lang }) {
  const done = isConfirmed(mention, voice.confirmed)
  const choose = (choice: KalChoice) => voice.confirm(mention, choice)
  return (
    <li data-testid={`voice-chip-${mention.id}`} data-state={done ? 'confirmed' : 'pending'} className={BOX}>
      <p className="text-sm font-medium">{ta('voice.chip.kal.ask', lang)}</p>
      {done ? (
        <Confirmed lang={lang} />
      ) : (
        <div className="flex gap-2">
          <Button data-testid={`voice-chip-kal-yesterday-${mention.id}`} variant="outline" className="flex-1" onClick={() => choose('yesterday')}>
            {ta('voice.chip.kal.yesterday', lang)}
          </Button>
          <Button data-testid={`voice-chip-kal-tomorrow-${mention.id}`} variant="outline" className="flex-1" onClick={() => choose('tomorrow')}>
            {ta('voice.chip.kal.tomorrow', lang)}
          </Button>
        </div>
      )}
    </li>
  )
}

function ValueChip({ mention, voice, lang, field }: { mention: Mention; voice: VoiceQuestion; lang: Lang; field: RefObject<HTMLTextAreaElement | null> }) {
  const done = isConfirmed(mention, voice.confirmed)
  return (
    <li data-testid={`voice-chip-${mention.id}`} data-state={done ? 'confirmed' : 'pending'} className={cn(BOX, done && 'border-paid bg-paid-soft')}>
      <p className="num text-md font-medium">{ta('ASK_MENTION_CHIP', lang, { value: mention.value ?? '' })}</p>
      {done ? (
        <Confirmed lang={lang} />
      ) : (
        <div className="flex gap-2">
          <Button data-testid={`voice-chip-right-${mention.id}`} className="flex-1" onClick={() => voice.confirm(mention)}>
            {ta('voice.chip.right', lang)}
          </Button>
          <Button data-testid={`voice-chip-change-${mention.id}`} variant="outline" className="flex-1" onClick={() => field.current?.focus()}>
            {ta('voice.chip.change', lang)}
          </Button>
        </div>
      )}
    </li>
  )
}

function TypeChip({ mention, lang }: { mention: Mention; lang: Lang }) {
  return (
    <li data-testid={`voice-chip-${mention.id}`} data-state="type" className={cn(BOX, 'border-referred bg-referred-soft')}>
      <p className="text-sm font-medium text-referred-ink">{ta('ASK_MENTION_WORDS', lang, { heard: mention.heard })}</p>
    </li>
  )
}

export function MentionChips({ voice, lang, field }: { voice: VoiceQuestion; lang: Lang; field: RefObject<HTMLTextAreaElement | null> }) {
  if (voice.mentions.length === 0) return null
  return (
    <div data-testid="voice-confirm" className="flex flex-col gap-2">
      <p className="text-sm font-medium">{ta('voice.confirm.intro', lang)}</p>
      <ul className="flex flex-col gap-2">
        {voice.mentions.map((mention) =>
          isKal(mention) ? <KalChip key={mention.id} mention={mention} voice={voice} lang={lang} /> : needsTyping(mention) ? <TypeChip key={mention.id} mention={mention} lang={lang} /> : <ValueChip key={mention.id} mention={mention} voice={voice} lang={lang} field={field} />,
        )}
      </ul>
      <p className="text-xs text-ink-3">{ta('voice.confirm.rule', lang)}</p>
    </div>
  )
}

/**
 * One answer (screens 5.2, fs-05 section 10): the scam banner when the check fired, the answer text, the clause chips
 * (H17), what it is based on with source badges, one next-action button chosen by the backend (H21), Listen, and a
 * footer with the mode word (H26) and the provider. The card never shows a number the server did not send, never a
 * confidence, and never text the model wrote outside the answer string, which the guard already passed.
 */
import { Volume2, VolumeX } from 'lucide-react'

import type { AskAnswer, NextActionKind } from '../api/ask'
import { ModeBadge } from '../components/ModeBadge'
import { SourceBadges } from '../components/SourceBadge'
import { ta } from '../copy/ask'
import type { Speaker } from '../components/voiceSpeaker'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { AskClauses } from './AskClauses'
import { AskDetails } from './AskDetails'
import { AskScamBanner } from './AskScamBanner'

type Props = {
  answer: AskAnswer
  answeredAt: string | null
  lang: Lang
  speaker: Speaker | null
  onNext: (kind: NextActionKind) => void
}

/** The answer starts with the scam sentence when the check fired; the banner already shows it, so the card keeps the rest. */
function bodyOf(answer: AskAnswer): string {
  if (!answer.scam_warning) return answer.answer
  const warning = ta('ASK_SCAM_WARNING', answer.lang)
  return answer.answer.startsWith(warning) ? answer.answer.slice(warning.length).trim() : answer.answer
}

function rulesVersionOf(answer: AskAnswer): string {
  const rules = answer.facts_used.flatMap((f) => f.sources).find((s) => s.kind === 'RULES')
  return rules?.ref.split(':')[1] ?? ''
}

function Listen({ answer, speaker, lang }: { answer: AskAnswer; speaker: Speaker; lang: Lang }) {
  const speaking = speaker.speakingId === answer.ask_id
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        data-testid={`ask-listen-${answer.ask_id}`}
        data-speaking={speaking ? 'true' : 'false'}
        variant="outline"
        aria-label={ta(speaking ? 'voice.state.speaking' : 'voice.btn.listen', lang)}
        onClick={() => (speaking ? speaker.stop() : void speaker.speak(answer))}
      >
        {speaking ? <VolumeX aria-hidden="true" /> : <Volume2 aria-hidden="true" />}
        {ta('voice.btn.listen', lang)}
      </Button>
      {speaking && speaker.state === 'speaking' ? <p className="text-xs text-ink-3">{ta('voice.state.speaking', lang)}</p> : null}
      {speaker.label !== null && speaker.label.mode !== 'LIVE' && speaker.speakingId !== null ? <ModeBadge mode={speaker.label.mode} testId="ask-listen-mode" /> : null}
    </div>
  )
}

export function AskAnswerCard({ answer, answeredAt, lang, speaker, onNext }: Props) {
  const body = bodyOf(answer)
  return (
    <div data-testid="ask-answer" data-ask-id={answer.ask_id} data-mode={answer.mode} className="flex flex-col gap-2">
      {answer.scam_warning ? <AskScamBanner lang={lang} /> : null}
      <Card className="py-4">
        <CardContent className="flex flex-col gap-3 px-4">
          {body === '' ? null : (
            <p data-testid="ask-answer-text" lang={answer.lang} className="whitespace-pre-line text-md">
              {body}
            </p>
          )}
          <AskClauses clauses={answer.clauses} lang={lang} />
          {answer.facts_used.length === 0 ? null : (
            <div data-testid="ask-facts" className="flex flex-col gap-2">
              <p className="text-xs font-medium text-ink-3">{ta('ask.based_on', lang)}</p>
              <ul className="flex flex-col gap-2">
                {answer.facts_used.map((fact) => (
                  <li key={fact.key} className="flex flex-col">
                    <span className="text-sm text-ink-2">
                      {lang === 'en' ? fact.label_en : fact.label_hi}: <span className="num font-medium text-foreground">{fact.value}</span>
                    </span>
                    <SourceBadges sources={fact.sources} rulesVersion={rulesVersionOf(answer)} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap items-start justify-between gap-2">
            <Button data-testid="ask-next" data-kind={answer.next_action.kind} size="lg" onClick={() => onNext(answer.next_action.kind)}>
              {ta(`next_action.${answer.next_action.kind}`, lang)}
            </Button>
            {speaker === null ? null : <Listen answer={answer} speaker={speaker} lang={lang} />}
          </div>
          <div data-testid="ask-footer" className="flex items-center justify-between gap-2 border-t pt-2">
            <span className="flex items-center gap-2 text-xs text-ink-3">
              <ModeBadge mode={answer.mode} testId="ask-mode" />
              <span lang="en" data-testid="ask-provider">{answer.provider}</span>
            </span>
            <AskDetails label={answer} answeredAt={answeredAt} lang={lang} askId={answer.ask_id} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

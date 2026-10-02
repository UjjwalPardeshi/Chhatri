/**
 * One grievance as a card with its ladder (fs-06 5.4 and 8.3, screens-and-flows 7.1): the topic and the case, then an
 * ordered list of steps, an `ol` with `aria-current="step"` on the active one. A step shows its name, one line on what
 * it is, its state, its clock (only where a source exists), its delivery note and, outside Chhatri, the marked contact
 * placeholder. The active step carries its sentence, "when to go on", and its buttons. Nothing here decides money.
 */
import { CircleCheck, Circle, CircleDot } from 'lucide-react'

import type { Grievance, LadderStep } from '../api/rights'
import { tr, type RightsCopyKey } from '../copy/rights'
import { cn } from '../lib/cn'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import { NetworkButton } from '../shell/SharedStates'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { activeLine, clockLine, escalation, isOutside, respondentKey, stateKey, type Escalation } from './grievanceModel'
import { lineText } from './rightsKit'

export type CardActions = {
  busy: boolean
  onEscalate: (grievance: Grievance, escalation: Escalation) => void
  onResolve: (grievance: Grievance) => void
  onGuide: (grievance: Grievance, step: LadderStep) => void
}

type StepProps = { grievance: Grievance; step: LadderStep; lang: Lang; now: string | null; actions: CardActions }

const MARK = { DONE: CircleCheck, ACTIVE: CircleDot, NOT_STARTED: Circle } as const

function StepButtons({ grievance, step, lang, now, actions }: StepProps) {
  const next = escalation(grievance, now)
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-ink-3">{tr('grv.when_next', lang)}</p>
      {next ? (
        <NetworkButton data-testid={`grv-escalate-${step.id}`} disabled={actions.busy} onClick={() => actions.onEscalate(grievance, next)}>
          {tr(next.key, lang)}
        </NetworkButton>
      ) : null}
      {step.id === 'BIMA_BHAROSA' ? (
        <Button data-testid="grv-how" variant="outline" onClick={() => actions.onGuide(grievance, step)}>
          {tr('grv.btn.how', lang)}
        </Button>
      ) : null}
      <NetworkButton data-testid={`grv-resolve-${step.id}`} variant="outline" disabled={actions.busy} onClick={() => actions.onResolve(grievance)}>
        {tr('grv.btn.resolved', lang)}
      </NetworkButton>
    </div>
  )
}

function Step(props: StepProps) {
  const { grievance, step, lang, now } = props
  const Mark = MARK[step.state]
  const active = step.state === 'ACTIVE' && grievance.status === 'OPEN'
  const sentence = activeLine(step, now, formatDate(step.entered_at, lang))
  const outside = isOutside(step)
  const stateLabel = active ? tr('grv.state.here', lang) : tr(stateKey(step), lang)
  return (
    <li data-testid={`grv-step-${step.id}`} data-state={step.state} aria-current={active ? 'step' : undefined} className={cn('flex flex-col gap-2 rounded-lg border p-3', active ? 'border-primary bg-accent' : 'bg-card')}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Mark className="mt-0.5 size-5 shrink-0 text-ink-2" aria-hidden="true" />
          <div className="flex flex-col">
            <span className="text-md font-medium">{tr(`grv.step.${step.id}` as RightsCopyKey, lang)}</span>
            <span className="text-sm text-ink-2">{tr(`grv.what.${step.id}` as RightsCopyKey, lang)}</span>
          </div>
        </div>
        <Badge variant={active ? 'default' : 'secondary'} data-testid={`grv-state-${step.id}`}>
          {stateLabel}
        </Badge>
      </div>
      {step.state === 'NOT_STARTED' ? null : (
        <>
          <p data-testid={`grv-clock-${step.id}`} className="text-sm">
            {lineText(clockLine(step), lang)}
          </p>
          {sentence ? (
            <p data-testid={`grv-sentence-${step.id}`} className="text-sm font-medium">
              {lineText(sentence, lang)}
            </p>
          ) : null}
        </>
      )}
      {outside ? (
        <div className="flex flex-col gap-1 text-xs text-ink-3">
          <span data-testid={`grv-delivery-${step.id}`} data-delivery={step.delivery}>
            {tr(step.delivery === 'SELF_REPORTED' ? 'grv.delivery.SELF_REPORTED' : 'grv.delivery.SIMULATED', lang)}
          </span>
          {step.state === 'NOT_STARTED' ? null : <span>{tr('grv.contact.placeholder', lang)}</span>}
        </div>
      ) : null}
      {step.id === 'BIMA_BHAROSA' && active ? (
        <div className="flex flex-col gap-1 text-xs text-ink-2">
          <span>{tr('grv.portal', lang)}</span>
          {grievance.decision_id && grievance.case_id ? <span>{tr('grv.bring', lang, { decision_id: grievance.decision_id, case_id: grievance.case_id })}</span> : null}
        </div>
      ) : null}
      {active ? <StepButtons {...props} /> : null}
    </li>
  )
}

export function GrievanceCard({ grievance, lang, now, actions }: { grievance: Grievance; lang: Lang; now: string | null; actions: CardActions }) {
  return (
    <Card data-testid="grv-card" data-grievance={grievance.grievance_id} data-status={grievance.status} className="py-4">
      <CardContent className="flex flex-col gap-3 px-4">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="grv-topic" className="text-md font-semibold">
              {tr(`grv.topic.${grievance.topic}` as RightsCopyKey, lang)}
            </span>
            {grievance.status === 'RESOLVED' ? <Badge variant="secondary">{tr('grv.resolved', lang)}</Badge> : null}
          </div>
          {grievance.case_id ? <span className="text-sm text-ink-2">{tr('grv.case', lang, { case_id: grievance.case_id })}</span> : null}
          <span className="text-xs text-ink-3">{tr(respondentKey(grievance.respondent), lang)}</span>
        </div>
        <ol aria-label={tr(`grv.topic.${grievance.topic}` as RightsCopyKey, lang)} className="flex flex-col gap-2">
          {grievance.ladder_steps.map((step) => (
            <Step key={step.id} grievance={grievance} step={step} lang={lang} now={now} actions={actions} />
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

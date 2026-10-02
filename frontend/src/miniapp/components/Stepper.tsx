/**
 * The claim stepper (fs-04 S5, design system 5.2): an ordered list of the five steps. Each step has an icon and a
 * word for its state (colour never works alone), the simulated time, the plain reason, and for Paid and the lender a
 * SIMULATED line. The step that is current carries `aria-current="step"`, and a polite live region says what is
 * happening now, so a change of state is heard as well as seen. The icon of a system that is working turns; under
 * reduced motion the global rule stops it, and the word stays.
 */
import { CircleCheck, CircleDashed, CircleMinus, CircleX, LoaderCircle, UserRound, type LucideIcon } from 'lucide-react'

import type { StepIcon, StepView } from '../hooks/trackerModel'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { formatClock } from '../lib/format'
import { useMiniapp } from '../shell/MiniappContext'
import { LineText } from './StepperLine'

const ICONS: Readonly<Record<StepIcon, LucideIcon>> = {
  done: CircleCheck,
  working: LoaderCircle,
  person: UserRound,
  waiting: CircleDashed,
  skipped: CircleMinus,
  stopped: CircleX,
}
const DISC: Readonly<Record<StepIcon, string>> = {
  done: 'bg-paid-soft text-paid-ink',
  working: 'bg-accent text-primary',
  person: 'bg-referred-soft text-referred-ink',
  waiting: 'bg-secondary text-ink-3',
  skipped: 'bg-secondary text-ink-3',
  stopped: 'bg-blocked-soft text-blocked',
}
const STATE_WORD: Readonly<Record<StepIcon, string>> = {
  done: 'text-paid-ink',
  working: 'text-primary',
  person: 'text-referred-ink',
  waiting: 'text-ink-3',
  skipped: 'text-ink-3',
  stopped: 'text-blocked',
}

/** What the live region says: the step that is happening now, else the last one that finished. */
function announcedStep(steps: readonly StepView[]): StepView | null {
  return steps.find((step) => step.status === 'current') ?? steps.findLast((step) => step.status === 'completed') ?? null
}

function Disc({ icon }: { icon: StepIcon }) {
  const Icon = ICONS[icon]
  return (
    <span className={cn('relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full', DISC[icon])}>
      <Icon className={cn('size-4', icon === 'working' && 'animate-spin')} aria-hidden="true" />
    </span>
  )
}

export function SimulatedLine({ kind }: { kind: 'payment' | 'lender' }) {
  const { lang } = useMiniapp()
  return (
    <p data-mode="SIMULATED" className="mt-2 inline-flex items-start gap-1.5 rounded-md bg-demo-soft px-2 py-1 text-xs text-demo">
      <CircleDashed className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
      <span>{t(kind === 'payment' ? 'sim.payment' : 'sim.lender', lang)}</span>
    </p>
  )
}

function StepRow({ step, last }: { step: StepView; last: boolean }) {
  const { lang } = useMiniapp()
  const time = formatClock(step.at)
  return (
    <li
      data-testid={`claim-step-${step.id}`}
      data-status={step.status}
      data-result={step.result ?? undefined}
      aria-current={step.status === 'current' ? 'step' : undefined}
      className="relative flex gap-3 pb-5 last:pb-0"
    >
      {last ? null : <span aria-hidden="true" className="absolute top-7 bottom-0 left-3.5 w-0.5 -translate-x-1/2 bg-border" />}
      <Disc icon={step.icon} />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-md font-medium leading-snug text-foreground">{t(step.titleKey, lang)}</h3>
          {step.at === null ? null : (
            <time dateTime={step.at} className="num shrink-0 text-caption text-ink-3">
              {time}
            </time>
          )}
        </div>
        <p className={cn('text-xs font-medium', STATE_WORD[step.icon])}>{t(step.stateKey, lang)}</p>
        {step.headline === null ? null : (
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2">
            <LineText line={step.headline} className="text-sm font-medium text-foreground" />
            {step.amountLabel === null ? null : <span className="num text-sm font-medium text-foreground">{step.amountLabel}</span>}
          </div>
        )}
        {step.detail === null ? null : <LineText line={step.detail} className="mt-0.5 text-caption text-ink-2" />}
        {step.simulated === null ? null : <SimulatedLine kind={step.simulated} />}
      </div>
    </li>
  )
}

export function Stepper({ steps }: { steps: readonly StepView[] }) {
  const { lang } = useMiniapp()
  const now = announcedStep(steps)
  return (
    <>
      <ol data-testid="claim-stepper" aria-label={t('tracker.steps_label', lang)} className="flex flex-col">
        {steps.map((step, index) => (
          <StepRow key={step.id} step={step} last={index === steps.length - 1} />
        ))}
      </ol>
      <output data-testid="claim-live" aria-live="polite" className="sr-only">
        {now === null ? '' : t('tracker.live_step', lang, { step: t(now.titleKey, lang), state: t(now.stateKey, lang) })}
      </output>
    </>
  )
}

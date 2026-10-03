/**
 * The parts of S5 (fs-04 8): the header (kind, day, status pill, amount), the case chip and its clock, the card of a
 * question about a payout, the actions, and the skeleton. Every word is a copy key or the API's own sentence, and the
 * amount is the API's label: a question about a payout shows the amount of the payout, unchanged, and never offers
 * another one.
 */
import { Link } from 'react-router'

import { LineText } from '../components/StepperLine'
import type { Clock as ClockValue, ClaimView } from '../hooks/trackerModel'
import { cn } from '../lib/cn'
import { t } from '../lib/copy'
import { formatDate, formatDateTime } from '../lib/format'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { NetworkButton } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Skeleton } from '../ui/skeleton'
import type { Dispute } from './ClaimDetailDispute'
import { ClaimsHeading } from './ClaimsHeading'
import { ClaimPill } from './ClaimsPill'

const BLOCK = 'flex flex-col gap-3 rounded-lg border bg-card p-4'

function clockText(clock: ClockValue, lang: Lang): string {
  switch (clock.kind) {
    case 'left':
      return t('tracker.clock.left', lang, { hours: clock.hours })
    case 'overdue':
      return t('tracker.clock.overdue', lang)
    case 'due':
      return t('tracker.clock.due', lang, { time: formatDateTime(clock.at, lang) })
  }
}

export function ClaimHeader({ view }: { view: ClaimView }) {
  const { lang } = useMiniapp()
  return (
    <section data-testid="claim-header" className={BLOCK}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <ClaimsHeading data-testid="claim-kind" className="text-md font-bold">
            {t(view.kindKey, lang)}
          </ClaimsHeading>
          <p data-testid="claim-date" className="text-caption text-muted-foreground">
            {formatDate(view.at, lang)}
          </p>
        </div>
        <ClaimPill pill={view.pill} testId="claim-pill" />
      </div>
      {view.amountLabel === null ? null : (
        <p data-testid="claim-amount" className="num text-4xl font-bold leading-none text-foreground">
          {view.amountLabel}
        </p>
      )}
    </section>
  )
}

/** "Sent to a claims officer · case C-2291": English in every language, because the catalogue has no Hindi line. */
export function CaseChip({ caseId }: { caseId: string }) {
  return (
    <div
      data-testid="claim-case-chip"
      tabIndex={-1}
      className="inline-flex w-fit max-w-full items-start gap-2 rounded-md bg-referred-soft px-3 py-2 text-referred-ink outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <LineText line={{ kind: 'copy', key: 'CASE_CHIP', params: { case_id: caseId } }} className="text-sm font-medium" />
    </div>
  )
}

export function ClaimClock({ clock }: { clock: ClockValue }) {
  const { lang } = useMiniapp()
  return (
    <p data-testid="claim-clock" className={cn('inline-flex items-center gap-1.5 text-caption font-medium', clock.kind === 'overdue' ? 'text-blocked' : 'text-ink-2')}>
      <span>{clockText(clock, lang)}</span>
    </p>
  )
}

/** The case of a claim with a person (REFERRED): the chip and the clock, under the steps. */
export function CaseBlock({ view }: { view: ClaimView }) {
  if (view.caseChip === null) return null
  return (
    <section className="flex flex-col items-start gap-2">
      <CaseChip caseId={view.caseChip.caseId} />
      {view.clock === null ? null : <ClaimClock clock={view.clock} />}
    </section>
  )
}

function Resolution({ note }: { note: string }) {
  const { lang } = useMiniapp()
  return (
    <div data-testid="claim-resolution" className="flex flex-col gap-0.5 rounded-lg bg-secondary p-3">
      <p className="text-xs font-medium text-muted-foreground">{t('tracker.officer_note', lang)}</p>
      <p lang={lang === 'en' ? undefined : 'en'} className="text-sm text-foreground">
        {note}
      </p>
    </div>
  )
}

/** A question about a payout: its status, the unchanged amount, the case chip and its clock while open (they say what the list line says), and once closed the line about the unchanged amount and the note. */
export function DisputeCard({ view }: { view: ClaimView }) {
  const { lang } = useMiniapp()
  const open = view.caseStatus === 'OPEN'
  return (
    <section data-testid="claim-dispute-card" data-status={view.pill.word} className={BLOCK}>
      <div className="flex items-start justify-between gap-3">
        <ClaimsHeading className="flex items-center gap-2 text-md font-bold">
          {t(view.kindKey, lang)}
        </ClaimsHeading>
        <ClaimPill pill={view.pill} testId="claim-dispute-pill" />
      </div>
      {view.amountLabel === null ? null : (
        <p data-testid="claim-dispute-amount" className="num text-2xl font-bold text-foreground">
          {view.amountLabel}
        </p>
      )}
      {open || view.nextLine === null ? null : <LineText line={view.nextLine} className="text-sm text-foreground" />}
      {open && view.caseChip !== null ? <CaseChip caseId={view.caseChip.caseId} /> : null}
      {open && view.clock !== null ? <ClaimClock clock={view.clock} /> : null}
      {!open && view.resolution !== null ? <Resolution note={view.resolution} /> : null}
    </section>
  )
}

const ACTION = 'h-auto min-h-11 flex-1 basis-36 py-2 whitespace-normal'

type ActionsProps = { view: ClaimView; showWhy: boolean; dispute: Dispute }

/** The receipt, "Why this amount?" where the next-step bar does not already carry it, and "This is wrong" on a paid claim. */
export function ClaimActions({ view, showWhy, dispute }: ActionsProps) {
  const { lang, url } = useMiniapp()
  const decision = view.decisionId
  if (decision === null && !view.canDispute) return null
  return (
    <div className="flex flex-wrap gap-3">
      {decision === null ? null : (
        <Button asChild variant="outline" className={ACTION}>
          <Link data-testid="claim-open-receipt" to={url.href({ screen: 'receipt', decision })}>
            {t('tracker.btn.receipt', lang)}
          </Link>
        </Button>
      )}
      {decision === null || !showWhy ? null : (
        <Button asChild variant="outline" className={ACTION}>
          <Link data-testid="claim-open-why" to={url.href({ screen: 'why', decision })}>
            {t('tracker.btn.why', lang)}
          </Link>
        </Button>
      )}
      {view.canDispute ? (
        <div className="flex flex-1 basis-36 flex-col gap-1.5">
          <NetworkButton
            data-testid="claim-dispute-button"
            variant="outline"
            className="h-auto min-h-11 w-full py-2 whitespace-normal"
            disabled={dispute.busy}
            aria-busy={dispute.busy ? true : undefined}
            onClick={dispute.send}
          >
            {t('tracker.btn.wrong', lang)}
          </NetworkButton>
          {dispute.failed ? (
            <p role="alert" data-testid="claim-dispute-error" className="text-caption text-blocked">
              {t('error.generic', lang)}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/** A header and five step rows, so nothing jumps when the claim arrives. */
export function ClaimSkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-4">
      <Skeleton className="h-24 w-full rounded-lg" />
      <div className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} data-testid="claim-skeleton-step" className="flex items-center gap-3">
            <Skeleton className="size-7 shrink-0 rounded-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ))}
      </div>
    </output>
  )
}

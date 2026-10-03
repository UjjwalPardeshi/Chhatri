/**
 * One card of S4 (fs-04 8): the kind of claim, its day, a status pill, the amount once there is one and one line on
 * what happens next. The card is a list item whose title is the link, stretched over the card, so the whole card is
 * one tap target and a screen reader meets one link. A question about a payout names the claim it is about and opens
 * that claim, where its card is drawn (it has no id of its own in the URL).
 */
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'

import type { ClaimView } from '../hooks/trackerModel'
import { t } from '../lib/copy'
import { formatDate } from '../lib/format'
import { LineText } from '../components/StepperLine'
import { useMiniapp } from '../shell/MiniappContext'
import { ClaimsHeading } from './ClaimsHeading'
import { ClaimPill } from './ClaimsPill'

export function ClaimsCard({ view }: { view: ClaimView }) {
  const { lang, url } = useMiniapp()
  const to = url.href(view.detailClaimId === null ? { screen: 'claims' } : { screen: 'claim', claim: view.detailClaimId })
  return (
    <li
      data-testid={`claim-card-${view.id}`}
      data-status={view.pill.word}
      className="relative flex flex-col gap-2 px-4 py-3 text-card-foreground focus-within:ring-[3px] focus-within:ring-inset focus-within:ring-ring/50 hover:bg-paper-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <ClaimsHeading className="text-md font-bold leading-snug">
            <Link to={to} className="outline-none after:absolute after:inset-0 after:content-['']">
              {t(view.kindKey, lang)}
            </Link>
          </ClaimsHeading>
          <p className="text-caption text-muted-foreground">
            <span>{formatDate(view.at, lang)}</span>
            {view.disputedClaimId === null ? null : <span> · {t('tracker.about_claim', lang, { claim_id: view.disputedClaimId })}</span>}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <div className="flex flex-col items-end gap-0.5">
            {view.amountLabel === null ? null : <span className="num text-xl font-bold leading-tight">{view.amountLabel}</span>}
            <ClaimPill pill={view.pill} />
          </div>
          <ChevronRight className="size-5 text-faint" aria-hidden="true" />
        </div>
      </div>
      {view.nextLine === null ? null : <LineText line={view.nextLine} className="text-caption text-ink-2" />}
    </li>
  )
}

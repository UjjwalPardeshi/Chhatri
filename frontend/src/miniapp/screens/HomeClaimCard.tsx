/**
 * The latest-claim card of Home (fs-04 S1): the kind of claim, its day, the amount the API recorded and one pill that
 * says where it stands, linking to the claim's detail (S5). The pill's words are the plain labels of fs-04 14.2 in the
 * language shown; `data-status` carries the engine word. A dispute opens the claim it is about. Nothing is computed here.
 */
import { ChevronRight, CircleCheck, CircleX, Clock, Hourglass, Scale, UserRound, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { ClaimItem } from '../../api/types'
import { t, type CopyKey } from '../lib/copy'
import { cn } from '../lib/cn'
import { formatDate } from '../lib/format'
import { useMiniapp } from '../shell/MiniappContext'
import { Badge } from '../ui/badge'
import { Card } from '../ui/card'

type Pill = { word: string; labelKey: CopyKey; tone: string; icon: LucideIcon }

const PAID = 'bg-paid-soft text-paid-ink'
const DECIDED = 'bg-decided-soft text-decided'
const REFERRED = 'bg-referred-soft text-referred-ink'
const BLOCKED = 'bg-blocked-soft text-blocked'
const NEUTRAL = 'bg-secondary text-secondary-foreground'

const KIND_KEYS: Readonly<Record<ClaimItem['kind'], CopyKey>> = {
  AREA: 'tracker.kind.area',
  PERSONAL: 'tracker.kind.personal',
  DISPUTE: 'tracker.kind.dispute',
}

const isCredited = (item: ClaimItem): boolean => item.steps.some((step) => step.name === 'Paid' && step.status === 'completed')

/** Where the claim stands, as the API recorded it (fs-04 14.2). A claim with no decision yet is "in progress", never "paid". */
export function claimPill(item: ClaimItem): Pill {
  if (item.kind === 'DISPUTE') {
    return item.case_status === 'OPEN'
      ? { word: 'DISPUTE_OPEN', labelKey: 'claim.status.question_open', tone: REFERRED, icon: Scale }
      : { word: 'DISPUTE_CLOSED', labelKey: 'claim.status.question_closed', tone: NEUTRAL, icon: CircleCheck }
  }
  switch (item.outcome) {
    case 'APPROVED':
      return isCredited(item)
        ? { word: 'APPROVED', labelKey: 'claim.status.paid', tone: PAID, icon: CircleCheck }
        : { word: 'APPROVED', labelKey: 'claim.status.approved_pending', tone: DECIDED, icon: Clock }
    case 'REFERRED':
      return { word: 'REFERRED', labelKey: 'claim.status.referred', tone: REFERRED, icon: UserRound }
    case 'DECLINED':
      return { word: 'DECLINED', labelKey: 'claim.status.declined', tone: BLOCKED, icon: CircleX }
    default:
      return item.kind === 'PERSONAL'
        ? { word: 'WAITING_FOR_SLIP', labelKey: 'claim.status.waiting_slip', tone: NEUTRAL, icon: Hourglass }
        : { word: 'IN_PROGRESS', labelKey: 'tracker.state.now', tone: NEUTRAL, icon: Clock }
  }
}

/** The claim the card opens: its own id, or the one a dispute is about; none for a claim with no id yet. */
export const claimLinkId = (item: ClaimItem): string | null => item.claim_id ?? item.disputed_claim_id

export function HomeClaimCard({ item }: { item: ClaimItem }) {
  const { lang, url, embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  const pill = claimPill(item)
  const id = claimLinkId(item)
  const to = url.href(id === null ? { screen: 'claims' } : { screen: 'claim', claim: id })
  return (
    <Card data-testid="home-latest-claim" data-status={pill.word} className="gap-0 overflow-hidden py-0">
      <Link to={to} className="flex min-h-14 flex-col gap-2 p-4 outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <span className="flex items-center justify-between gap-2">
          <Title className="text-caption font-medium text-muted-foreground">{t('home.latest', lang)}</Title>
          <Badge variant="secondary" data-testid="home-latest-claim-pill" className={cn('gap-1', pill.tone)}>
            <pill.icon aria-hidden="true" />
            {t(pill.labelKey, lang)}
          </Badge>
        </span>
        <span className="flex items-end justify-between gap-3">
          <span className="flex min-w-0 flex-col">
            <span className="text-md font-medium">{t(KIND_KEYS[item.kind], lang)}</span>
            <span className="text-caption text-muted-foreground">{formatDate(item.claim_at, lang)}</span>
          </span>
          <span className="flex items-center gap-1">
            {item.amount_label ? <span className="num text-xl font-medium">{item.amount_label}</span> : null}
            <ChevronRight className="size-5 text-muted-foreground" aria-hidden="true" />
          </span>
        </span>
      </Link>
    </Card>
  )
}

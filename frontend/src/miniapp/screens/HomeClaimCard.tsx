/**
 * The latest-claim card of Home (fs-04 S1): the kind of claim, its day, the amount the API recorded and one pill that
 * says where it stands, linking to the claim's detail (S5). The pill's words are the plain labels of fs-04 14.2 in the
 * language shown; `data-status` carries the engine word. A dispute opens the claim it is about. Nothing is computed here.
 */

import type { ClaimItem } from '../../api/types'
import { t, type CopyKey } from '../lib/copy'
import { formatDate } from '../lib/format'
import { ListGroup, ListRowLink, SectionLabel } from '../components/ListRow'
import { StatusWord, type StatusTone } from '../components/StatusWord'
import { useMiniapp } from '../shell/MiniappContext'

type Pill = { word: string; labelKey: CopyKey; tone: StatusTone }

const PAID = 'paid'
const DECIDED = 'decided'
const REFERRED = 'referred'
const BLOCKED = 'blocked'
const NEUTRAL = 'neutral'

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
      ? { word: 'DISPUTE_OPEN', labelKey: 'claim.status.question_open', tone: REFERRED }
      : { word: 'DISPUTE_CLOSED', labelKey: 'claim.status.question_closed', tone: NEUTRAL }
  }
  switch (item.outcome) {
    case 'APPROVED':
      return isCredited(item)
        ? { word: 'APPROVED', labelKey: 'claim.status.paid', tone: PAID }
        : { word: 'APPROVED', labelKey: 'claim.status.approved_pending', tone: DECIDED }
    case 'REFERRED':
      return { word: 'REFERRED', labelKey: 'claim.status.referred', tone: REFERRED }
    case 'DECLINED':
      return { word: 'DECLINED', labelKey: 'claim.status.declined', tone: BLOCKED }
    default:
      return item.kind === 'PERSONAL'
        ? { word: 'WAITING_FOR_SLIP', labelKey: 'claim.status.waiting_slip', tone: NEUTRAL }
        : { word: 'IN_PROGRESS', labelKey: 'tracker.state.now', tone: NEUTRAL }
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
    <section data-testid="home-latest-claim" data-status={pill.word} className="flex flex-col gap-2">
      <SectionLabel as={Title}>{t('home.latest', lang)}</SectionLabel>
      <ListGroup>
        <ListRowLink
          to={to}
          title={t(KIND_KEYS[item.kind], lang)}
          secondary={
            <span className="flex flex-wrap items-center gap-x-2">
              <span>{formatDate(item.claim_at, lang)}</span>
              <StatusWord tone={pill.tone} data-testid="home-latest-claim-pill">
                {t(pill.labelKey, lang)}
              </StatusWord>
            </span>
          }
          trailing={item.amount_label ? <span className="num text-xl font-bold">{item.amount_label}</span> : null}
        />
      </ListGroup>
    </section>
  )
}

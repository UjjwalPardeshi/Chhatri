/**
 * S4 Claims (fs-04 8, screens and flows 4.4): one list of everything Chhatri is doing or has done for the
 * merchant's money, newest first, as the API sends it. A claim that cannot exist (an AREA claim that is REFERRED)
 * is a contract violation and shows the error state with its code. The screen computes nothing: the model words
 * each card, and the next-best bar says what to do next (`open_latest`, or `see_coverage_empty` with no claims).
 */
import { useClaimViews } from '../hooks/trackerModelContext'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims } from '../hooks/useMiniappData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { EmptyState, ResourceScreen } from '../shell/SharedStates'
import { Skeleton } from '../ui/skeleton'
import { ClaimsCard } from './ClaimsCard'

function ClaimCardSkeletons() {
  return (
    <div data-testid="app-skeleton" className="flex flex-col gap-3">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  )
}

export function Claims() {
  const { merchantId, lang } = useMiniapp()
  const claims = useClaims(merchantId)
  const { views, error } = useClaimViews(claims.data)
  const shown = error === null ? claims : { ...claims, data: null, error, state: 'error' as const }
  const ready = shown.data !== null && (shown.state === 'ready' || shown.state === 'offline' || shown.state === 'empty')
  useNextBest(ready ? { screen: 'claims', cover: null, claims: shown.data ?? [] } : null)
  return (
    <ResourceScreen
      name="claims"
      resource={shown}
      skeleton={<ClaimCardSkeletons />}
      empty={
        <div data-testid="claims-empty">
          <EmptyState message={t('empty.claims', lang)} />
        </div>
      }
    >
      {() => (
        <ul data-testid="claims-list" className="flex flex-col gap-3">
          {views.map((view) => (
            <ClaimsCard key={view.id} view={view} />
          ))}
        </ul>
      )}
    </ResourceScreen>
  )
}

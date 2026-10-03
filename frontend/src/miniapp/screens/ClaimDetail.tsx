/**
 * S5 Claim detail (fs-04 8, screens and flows 4.5, H1): where one claim is, in five steps, with a plain reason at each
 * step. The tracker model words every step from what the API recorded; this screen only lays them out. A question
 * about the claim's payout is its own card above the steps, and once the payout is credited "What happens next" sits
 * there too. An id that matches nothing is "not found" with a way back.
 */
import { useMemo } from 'react'

import { Stepper } from '../components/Stepper'
import { findClaim } from '../hooks/trackerModel'
import { useClaimViews } from '../hooks/trackerModelContext'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims } from '../hooks/useMiniappData'
import { useMiniapp } from '../shell/MiniappContext'
import { ResourceScreen, ScreenRoot } from '../shell/SharedStates'
import { useDispute } from './ClaimDetailDispute'
import { ClaimNextCard } from './ClaimDetailNext'
import { CaseBlock, ClaimActions, ClaimHeader, ClaimSkeleton, DisputeCard } from './ClaimDetailParts'
import { NotFoundCard } from './ClaimsNotFound'

export function ClaimDetail() {
  const { merchantId, lang, url } = useMiniapp()
  const wanted = url.claim
  const claims = useClaims(merchantId)
  const { views, error } = useClaimViews(claims.data)
  const dispute = useDispute({ merchantId, lang, reload: claims.reload })
  const shown = error === null ? claims : { ...claims, data: null, error, state: 'error' as const }
  const items = shown.data
  const view = useMemo(() => views.find((candidate) => candidate.claimId === wanted) ?? null, [views, wanted])
  const question = useMemo(() => views.find((candidate) => candidate.kind === 'DISPUTE' && candidate.disputedClaimId === wanted) ?? null, [views, wanted])
  const loaded = items !== null && (shown.state === 'ready' || shown.state === 'offline' || shown.state === 'empty')
  const item = loaded && wanted !== null ? findClaim(items, wanted) : null
  const nba = useNextBest(loaded && item !== null ? { screen: 'claim', cover: null, claims: items, claim: item } : null)

  if (wanted === null || (loaded && view === null)) {
    return (
      <ScreenRoot name="claim" state="error">
        <NotFoundCard />
      </ScreenRoot>
    )
  }
  return (
    <ResourceScreen name="claim" resource={shown} skeleton={<ClaimSkeleton />}>
      {() =>
        view === null ? null : (
          <>
            <ClaimHeader view={view} />
            {question === null ? null : <DisputeCard view={question} />}
            {view.paid && view.decisionId !== null ? <ClaimNextCard decisionId={view.decisionId} canDispute={view.canDispute} /> : null}
            <section className="rounded-lg border bg-card p-4">
              <Stepper steps={view.steps} />
            </section>
            <CaseBlock view={view} />
            <ClaimActions view={view} showWhy={nba?.id !== 'see_why'} dispute={dispute} />
          </>
        )
      }
    </ResourceScreen>
  )
}

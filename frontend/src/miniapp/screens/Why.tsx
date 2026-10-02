/**
 * S6 Why this amount (fs-04 8, screens and flows 4.6, H2 and H14): the engine's own explanation of one decision, the
 * formula in the language shown, each number with its sources, and what would have changed the result, exactly as the
 * receipt sends it. A decision that went to a person, or was not paid, has no amount: the screen says why in plain words
 * instead. "This is wrong" leads to the claim, where the dispute button is, because the question belongs to a payout.
 */
import { Scale } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router'

import type { Receipt } from '../../api/types'
import { CounterfactualCard } from '../components/CounterfactualCard'
import { canDispute } from '../hooks/trackerModel'
import { focusWhenPresent, useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useReceipt } from '../hooks/useMiniappData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { ResourceScreen, ScreenRoot } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { isNotFound, NotFoundCard } from './ClaimsNotFound'
import { claimOfReceipt } from './ReceiptRows'
import { reasonKeys } from './WhyReasons'
import { WhyFormula, WhyNoAmount, WhyNumbers, WhySkeleton } from './WhyParts'
import { whyRows } from './WhyRows'

function DisputeLink({ claimId }: { claimId: string }) {
  const { lang, url } = useMiniapp()
  const navigate = useNavigate()
  return (
    <Button
      data-testid="why-dispute"
      variant="outline"
      className="h-auto min-h-11 w-full py-2 whitespace-normal"
      onClick={() => {
        void navigate(url.href({ screen: 'claim', claim: claimId }))
        focusWhenPresent('claim-dispute-button')
      }}
    >
      <Scale aria-hidden="true" />
      {t('tracker.btn.wrong', lang)}
    </Button>
  )
}

function WhyBody({ receipt, claimId }: { receipt: Receipt; claimId: string | null }) {
  const { decision, explanation, counterfactuals } = receipt
  const lines = reasonKeys(receipt)
  return (
    <>
      {decision.outcome === 'APPROVED' ? (
        <>
          <WhyFormula en={explanation.formula_en} hi={explanation.formula_hi} />
          {explanation.facts.length === 0 ? null : <WhyNumbers rows={whyRows(explanation.facts)} rulesVersion={decision.rules_version} />}
        </>
      ) : (
        <WhyNoAmount
          heading={decision.outcome === 'REFERRED' ? 'why.person_heading' : 'claim.status.declined'}
          intro={decision.outcome === 'REFERRED' ? 'why.no_amount' : null}
          lines={lines}
        />
      )}
      <CounterfactualCard items={counterfactuals} testId="why-counterfactual" />
      {claimId === null ? null : <DisputeLink claimId={claimId} />}
    </>
  )
}

export function Why() {
  const { merchantId, url } = useMiniapp()
  const receipt = useReceipt(merchantId, url.decision)
  const claims = useClaims(merchantId)
  const claim = useMemo(() => claimOfReceipt(claims.data, receipt.data), [claims.data, receipt.data])
  const loaded = receipt.data !== null && (receipt.state === 'ready' || receipt.state === 'offline')
  useNextBest(loaded && claim !== null && claims.data !== null ? { screen: 'why', cover: null, claims: claims.data, claim } : null)
  if (receipt.state === 'error' && isNotFound(receipt.error)) {
    return (
      <ScreenRoot name="why" state="error">
        <NotFoundCard />
      </ScreenRoot>
    )
  }
  const disputable = claim !== null && claims.data !== null && canDispute(claim, claims.data) ? claim.claim_id : null
  return (
    <ResourceScreen name="why" resource={receipt} skeleton={<WhySkeleton />}>
      {(data) => <WhyBody receipt={data} claimId={disputable} />}
    </ResourceScreen>
  )
}

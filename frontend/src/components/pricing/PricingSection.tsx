/**
 * "Price the cover" (business model §3, flag h24_whatif): the pricing simulator at the end of the Backtest page. A judge
 * moves the product's levers (index floor, payout share, area daily cap, loading) and GET /api/pricing prices every
 * zone from the backtest's triggers; the section shows the chosen zone (Anil's Z7 first) and the city. Read-only:
 * nothing is saved. Without the backend's pricing table (always so in mock mode) the route answers 404 and the section
 * says so instead of showing a price. `/backtest#pricing` scrolls here once the page above has rendered.
 */
import { useId, useState } from 'react'

import type { ApiError } from '../../api/client'
import type { LeverKey, PricingLevers } from '../../api/pricing'
import { useHashScroll } from '../../state/useHashScroll'
import { AsyncView } from '../common/Status'
import { PricingControls } from './PricingControls'
import { PricingResults } from './PricingResults'
import { DEFAULT_ZONE, isUnavailable, PRICING_CAPTION, PRICING_READ_ONLY, PRICING_UNAVAILABLE, publishedLevers, withLever } from './pricingModel'
import { usePricing } from './usePricing'
import '../../styles/pricing.css'

const PRICING_SECTION_ID = 'pricing'

function Unavailable({ error }: { error: ApiError }) {
  return (
    <div className="status-box pricing__unavailable" data-testid="pricing-unavailable">
      <span className="status-box__title">{PRICING_UNAVAILABLE}</span>
      <span>{error.message}</span>
    </div>
  )
}

/** `pageReady`: everything above has rendered, so a deep link can scroll here without the page moving under it. */
export function PricingSection({ pageReady }: { pageReady: boolean }) {
  const headingId = useId()
  const [draft, setDraft] = useState<PricingLevers | null>(null)
  const [zoneId, setZoneId] = useState(DEFAULT_ZONE)
  const { answer, error, loading, retry } = usePricing(draft)
  useHashScroll(PRICING_SECTION_ID, pageReady && (answer !== null || error !== null))
  /** On top of the latest draft (else the levers priced), so two changes in one frame never undo each other. */
  const setLever = (priced: PricingLevers) => (key: LeverKey, value: number) => setDraft((current) => withLever(current ?? priced, key, value))
  return (
    <section id={PRICING_SECTION_ID} className="card section pricing" aria-labelledby={headingId} aria-busy={loading}>
      <header className="pricing__head">
        <h2 id={headingId}>Price the cover</h2>
        <p className="pricing__readonly">{PRICING_READ_ONLY}</p>
        {answer !== null && loading ? <p className="pricing__busy">Recomputing…</p> : null}
      </header>
      {answer === null && error !== null && isUnavailable(error) ? (
        <Unavailable error={error} />
      ) : (
        <AsyncView data={answer} error={error} loading={loading} reload={retry} label="Pricing the cover…">
          {(data) => (
            <div className="pricing__body">
              <PricingControls answer={data} levers={draft ?? data.levers} onLever={setLever(data.levers)} onReset={() => setDraft(publishedLevers(data.rules))} />
              <PricingResults answer={data} zoneId={zoneId} onZone={setZoneId} />
            </div>
          )}
        </AsyncView>
      )}
      <p className="pricing__caption">{PRICING_CAPTION}</p>
    </section>
  )
}

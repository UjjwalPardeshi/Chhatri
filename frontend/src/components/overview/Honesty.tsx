/**
 * What is real, what can be live and what is always simulated (SPEC §0.1, deck slide 13 "What
 * is live in our prototype"), beside the technology it describes. The live count is read from
 * GET /api/integrations at render time; each integration's status stays folded away until asked.
 */
import { useState } from 'react'

import { HONESTY_TIERS } from '../../content/deck'
import { useLive } from '../../state/live'
import { ErrorState, Loading } from '../common/Status'
import { Badge, integrationCounts } from '../layout/IntegrationBadges'

function LiveCount() {
  const { integrations, integrationsError } = useLive()
  if (integrationsError) return <span className="tier__now">Live status unavailable right now.</span>
  if (!integrations) return <span className="tier__now">Checking what is live…</span>
  const { live, simulated } = integrationCounts(integrations)
  return (
    <span className="tier__now num">
      Right now: {live} live, {simulated} simulated.
    </span>
  )
}

export function Tiers() {
  const tiers = [
    { key: 'real', ...HONESTY_TIERS.real, extra: null },
    { key: 'keyed', ...HONESTY_TIERS.keyed, extra: <LiveCount /> },
    { key: 'simulated', ...HONESTY_TIERS.simulated, extra: null },
  ]
  return (
    <div className="tiers" aria-label="What is live in our prototype">
      {tiers.map((tier) => (
        <div key={tier.key} className={`tier tier--${tier.key}`}>
          <p className="tier__title">{tier.title}</p>
          <p className="tier__text">
            {tier.text} {tier.extra}
          </p>
        </div>
      ))}
    </div>
  )
}

/** Every integration's mode and detail (LIVE green / SIMULATED grey), folded until opened. */
export function LiveNow() {
  const { integrations, integrationsError } = useLive()
  const [open, setOpen] = useState(false)
  if (integrationsError) return <ErrorState error={integrationsError} title="Integration status unavailable" />
  if (!integrations) return <Loading label="Checking integrations…" />
  return (
    <div className="live-now" data-open={open}>
      <button type="button" className="live-now__toggle" aria-expanded={open} aria-controls="integration-grid" onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide the list' : `Show each integration (${integrations.length})`}
      </button>
      <ul className="integration-grid" id="integration-grid">
        {integrations.map((status) => (
          <Badge key={status.name} status={status} />
        ))}
      </ul>
    </div>
  )
}

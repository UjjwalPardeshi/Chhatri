/**
 * Technology (deck slide 9) and what is live right now (SPEC §0.1: GET /api/integrations, LIVE
 * green / SIMULATED grey with the detail; nothing simulated is presented as live).
 */
import { useState } from 'react'

import { ACTIONS, CONTROL, REASONING, SIGNALS, STACK } from '../../content/deck'
import { useLive } from '../../state/live'
import { ErrorState, Loading } from '../common/Status'
import { Badge, integrationCounts } from '../layout/IntegrationBadges'
import { RevealSection } from './Reveal'

function LiveNow() {
  const { integrations, integrationsError } = useLive()
  const [open, setOpen] = useState(false)
  if (integrationsError) return <ErrorState error={integrationsError} title="Integration status unavailable" />
  if (!integrations) return <Loading label="Checking integrations…" />
  const { live, simulated } = integrationCounts(integrations)
  return (
    <div className="live-now" data-open={open}>
      <p className="ov-label">
        Running right now: <strong className="num">{live}</strong> live, <strong className="num">{simulated}</strong> simulated and labelled
      </p>
      <button type="button" className="live-now__toggle" aria-expanded={open} aria-controls="integration-grid" onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide the list' : 'Show each integration'}
      </button>
      <ul className="integration-grid" id="integration-grid">
        {integrations.map((status) => (
          <Badge key={status.name} status={status} />
        ))}
      </ul>
    </div>
  )
}

export function Tech() {
  return (
    <RevealSection label="Technology" className="ov-tech" tone="white">
      <h2 className="ov-h2">Statistics measure the loss, AI talks to people, code controls the money.</h2>
      <div className="tech">
        <div className="tech__col">
          <p className="tech__head">Signals</p>
          <ul className="tech__signals">
            {SIGNALS.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="tech__col">
          <p className="tech__head">Reasoning + memory</p>
          {REASONING.map((r) => (
            <div key={r.title} className="tech__card">
              <strong>{r.title}</strong>
              <span>{r.text}</span>
            </div>
          ))}
        </div>
        <div className="tech__col">
          <p className="tech__head">Control</p>
          <div className="tech__control">
            <strong>Policy engine</strong>
            {CONTROL.slice(0, 2).map((c) => (
              <span key={c}>{c}</span>
            ))}
            <span className="tech__only">The only layer that can approve a payout</span>
            <span>{CONTROL[2]}</span>
          </div>
        </div>
        <div className="tech__col">
          <p className="tech__head">Action</p>
          {ACTIONS.map((a) => (
            <div key={a.title} className="tech__card">
              <strong>{a.title}</strong>
              <span>{a.text}</span>
            </div>
          ))}
        </div>
      </div>
      <ul className="stack" aria-label="Stack">
        {STACK.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
      <LiveNow />
    </RevealSection>
  )
}

/**
 * Integration badges (SPEC §0.1, §19 GET /api/integrations, §20 header): LIVE green, SIMULATED
 * grey, each with its detail. The header shows two pills (LIVE n, SIMULATED n); the popover lists
 * every integration with its detail.
 */
import { useEffect, useRef, useState } from 'react'

import type { IntegrationName, IntegrationStatus } from '../../api/types'
import { useLive } from '../../state/live'

export const INTEGRATION_LABELS: Readonly<Record<IntegrationName, string>> = Object.freeze({
  sarvam_stt: 'Sarvam STT',
  sarvam_tts: 'Sarvam TTS',
  sarvam_chat: 'Sarvam chat',
  sarvam_vision: 'Sarvam vision',
  whatsapp: 'WhatsApp',
  paytm: 'Paytm link',
  n8n: 'n8n',
  memory: 'Cognee memory',
  weather: 'Open-Meteo',
  soundbox: 'Soundbox',
  sales_data: 'Sales data',
  alerts: 'Alerts feed',
  payout_rail: 'Payout rail',
  lender: 'Lender',
  kyc: 'KYC',
})

/** LIVE / SIMULATED counts (SPEC §0.1): the header pills and the Overview's honest tiers. */
export function integrationCounts(integrations: readonly IntegrationStatus[]): { live: number; simulated: number } {
  const live = integrations.filter((i) => i.mode === 'LIVE').length
  return { live, simulated: integrations.length - live }
}

export function Badge({ status }: { status: IntegrationStatus }) {
  const live = status.mode === 'LIVE'
  return (
    <li className={`integration ${live ? 'integration--live' : 'integration--sim'}`} data-mode={status.mode} data-name={status.name} title={status.detail}>
      <span className="integration__dot" />
      <span className="integration__name">{INTEGRATION_LABELS[status.name] ?? status.name}</span>
      <span className="integration__mode">{live ? 'LIVE' : 'SIMULATED'}</span>
      <span className="integration__detail">{status.detail}</span>
    </li>
  )
}

export function IntegrationBadges() {
  const { integrations, integrationsError } = useLive()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  if (integrationsError) {
    return (
      <span className="integrations-summary integrations-summary--error" role="alert" title={integrationsError.describe()}>
        Integrations unavailable
      </span>
    )
  }
  if (!integrations) return <span className="integrations-summary integrations-summary--loading">Integrations…</span>
  const { live, simulated } = integrationCounts(integrations)
  return (
    <div className="integrations" ref={rootRef}>
      <button type="button" className="integrations-summary" aria-expanded={open} aria-label={`${live} live · ${simulated} simulated`} title="What is live and what is simulated" onClick={() => setOpen((v) => !v)}>
        <span className="integrations-summary__seg integrations-summary__seg--live" data-count={live}>
          <span className="integrations-summary__glyph" aria-hidden="true" />
          LIVE <strong>{live}</strong>
        </span>
        <span className="integrations-summary__seg integrations-summary__seg--sim">
          SIMULATED <strong>{simulated}</strong>
        </span>
      </button>
      {open ? (
        <section className="integrations-popover card" aria-label="Integrations">
          <p className="integrations-popover__title">Live vs simulated</p>
          <ul className="integration-list">
            {integrations.map((status) => (
              <Badge key={status.name} status={status} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

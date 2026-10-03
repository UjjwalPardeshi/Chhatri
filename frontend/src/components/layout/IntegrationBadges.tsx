/**
 * Integration badges (SPEC §0.1, §19 GET /api/integrations, §20 header): LIVE green, SIMULATED
 * grey, each with its detail. The header names what is live (up to three green chips such as
 * "Sarvam", "WhatsApp", "Paytm") and then a grey "+N simulated"; with nothing live it reads
 * "Simulated · 17" rather than a zero count. The popover lists every integration with its detail.
 */
import { useEffect, useRef, useState } from 'react'

import type { IntegrationName, IntegrationStatus } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { useLive } from '../../state/live'
import { ProviderPanel } from './ProviderPanel'

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
  gemini_chat: 'Gemini chat',
  gemini_vision: 'Gemini vision',
  telegram: 'Telegram bot',
})

/** The product name a live integration shows as in the header (several Sarvam services are one "Sarvam"). */
export const INTEGRATION_BRANDS: Readonly<Record<IntegrationName, string>> = Object.freeze({
  sarvam_stt: 'Sarvam',
  sarvam_tts: 'Sarvam',
  sarvam_chat: 'Sarvam',
  sarvam_vision: 'Sarvam',
  whatsapp: 'WhatsApp',
  paytm: 'Paytm',
  n8n: 'n8n',
  memory: 'Cognee',
  weather: 'Open-Meteo',
  soundbox: 'Soundbox',
  sales_data: 'Sales data',
  alerts: 'Alerts',
  payout_rail: 'Payout rail',
  lender: 'Lender',
  kyc: 'KYC',
  gemini_chat: 'Gemini',
  gemini_vision: 'Gemini',
  telegram: 'Telegram',
})

/** Named header chips: at most this many live products are named before "+N". */
export const MAX_LIVE_CHIPS = 3

/** Distinct product names of the LIVE integrations, in API order. */
export function liveBrands(integrations: readonly IntegrationStatus[]): string[] {
  const names = integrations.filter((i) => i.mode === 'LIVE').map((i) => INTEGRATION_BRANDS[i.name] ?? i.name)
  return [...new Set(names)]
}

/** LIVE / SIMULATED / FALLBACK counts (SPEC §0.1, fs-08 9.1): the header summary and the Overview's honest tiers. */
export function integrationCounts(integrations: readonly IntegrationStatus[]): { live: number; simulated: number; fallback: number } {
  const count = (mode: IntegrationStatus['mode']) => integrations.filter((i) => i.mode === mode).length
  return { live: count('LIVE'), simulated: count('SIMULATED'), fallback: count('FALLBACK') }
}

/** True while any component is forced to its fallback path (the "forced" chip, so a presenter cannot forget it). */
export const anyForced = (integrations: readonly IntegrationStatus[]): boolean => integrations.some((i) => i.forced)

export function Badge({ status }: { status: IntegrationStatus }) {
  const live = status.mode === 'LIVE'
  const tone = live ? 'live' : status.mode === 'FALLBACK' ? 'fallback' : 'sim'
  return (
    <li className={`integration integration--${tone}`} data-mode={status.mode} data-name={status.name} title={status.detail}>
      <span className="integration__dot" />
      <span className="integration__name">{INTEGRATION_LABELS[status.name] ?? status.name}</span>
      <span className="integration__mode">{status.mode}</span>
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
  const { live, simulated, fallback } = integrationCounts(integrations)
  const panelOn = isFeatureEnabled('x6_provider_panel')
  const forced = panelOn && anyForced(integrations)
  const brands = liveBrands(integrations)
  const named = brands.slice(0, MAX_LIVE_CHIPS)
  const moreLive = brands.length - named.length
  return (
    <div className="integrations" ref={rootRef}>
      <button type="button" className="integrations-summary" data-live={live} aria-expanded={open} aria-label={`${live} live · ${simulated} simulated${fallback > 0 ? ` · ${fallback} fallback` : ''}${forced ? ' · forced' : ''}`} title="What is live and what is simulated" onClick={() => setOpen((v) => !v)}>
        {named.length > 0 ? (
          <span className="integrations-summary__seg integrations-summary__seg--live">
            {named.map((brand) => (
              <span key={brand} className="integrations-summary__chip">
                <span className="integrations-summary__glyph" aria-hidden="true" />
                {brand}
              </span>
            ))}
            {moreLive > 0 ? <span className="integrations-summary__more num">+{moreLive}</span> : null}
          </span>
        ) : null}
        <span className="integrations-summary__seg integrations-summary__seg--sim">
          {named.length > 0 ? (
            <>
              +<strong>{simulated}</strong> simulated
            </>
          ) : (
            <>
              Simulated · <strong>{simulated}</strong>
            </>
          )}
        </span>
        {fallback > 0 ? (
          <span className="integrations-summary__seg integrations-summary__seg--fallback">
            <span aria-hidden="true">▲</span>
            <strong>{fallback}</strong> fallback
          </span>
        ) : null}
        {forced ? <span className="integrations-summary__seg integrations-summary__seg--forced">forced</span> : null}
      </button>
      {open ? (
        <section className="integrations-popover card" aria-label="Integrations">
          {panelOn ? (
            <ProviderPanel integrations={integrations} />
          ) : (
            <>
              <p className="integrations-popover__title">Live vs simulated</p>
              <ul className="integration-list">
                {integrations.map((status) => (
                  <Badge key={status.name} status={status} />
                ))}
              </ul>
            </>
          )}
        </section>
      ) : null}
    </div>
  )
}

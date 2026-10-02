/**
 * The X6 provider panel (fs-08 section 9, card 4.5): one row per component with its mode badge, detail, provider and
 * model, the reason in words when it is not LIVE, the last call, and a "Force fallback" switch that works in demo mode.
 * "Clear all" releases every forced component; the footer lists the feature flags that are on in this build.
 */
import { useState } from 'react'

import type { IntegrationStatus } from '../../api/types'
import { enabledFeatures } from '../../features'
import { providerLine, reasonWords } from '../../lib/providerLabels'
import { useLive } from '../../state/live'
import { toApiError } from '../../state/useAsync'
import { ModeWord } from '../common/ModeChip'
import { INTEGRATION_LABELS } from './IntegrationBadges'

const MOCK_REASON = 'static demo: nothing live to force'

/** Why a row's switch is disabled, in words. */
export function switchReason(status: IntegrationStatus, mock: boolean): string {
  if (mock) return MOCK_REASON
  if (status.mode === 'SIMULATED' && status.provider) return 'no key set, already simulated'
  return 'no fallback path'
}

function lastCallText(status: IntegrationStatus): string | null {
  const call = status.last_call
  if (!call) return null
  return call.ms === null ? `last call: ${call.outcome}` : `last call: ${call.outcome}, ${call.ms} ms`
}

type RowProps = { status: IntegrationStatus; mock: boolean; busy: boolean; onSwitch: (status: IntegrationStatus) => void }

export function ProviderRow({ status, mock, busy, onSwitch }: RowProps) {
  const label = INTEGRATION_LABELS[status.name] ?? status.name
  const reason = status.mode === 'LIVE' ? null : reasonWords(status.fallback_reason)
  const who = providerLine(status)
  const call = lastCallText(status)
  const disabledWhy = status.switchable ? null : switchReason(status, mock)
  return (
    <li className={`provider-row provider-row--${status.mode.toLowerCase()}`} data-mode={status.mode} data-name={status.name} data-forced={status.forced ? 'true' : 'false'}>
      <span className="provider-row__head">
        <span className="provider-row__name">{label}</span>
        <ModeWord mode={status.mode} />
      </span>
      <span className="provider-row__detail">{status.detail}</span>
      <span className="provider-row__meta">
        {who ? <span className="provider-row__who">{who}</span> : null}
        {reason ? <span className="provider-row__reason">{reason}</span> : null}
        {call ? <span className="provider-row__call num">{call}</span> : null}
        {disabledWhy ? <span className={mock ? 'provider-row__why visually-hidden' : 'provider-row__why'}>{disabledWhy}</span> : null}
      </span>
      <span className="provider-row__switch">
        <button
          type="button"
          className="provider-switch"
          aria-label={`${status.forced ? 'Release' : 'Force fallback'}: ${label}`}
          aria-pressed={Boolean(status.forced)}
          disabled={!status.switchable || busy}
          title={disabledWhy ?? undefined}
          onClick={() => onSwitch(status)}
        >
          {status.forced ? 'Release' : 'Force fallback'}
        </button>
      </span>
    </li>
  )
}

export function ProviderPanel({ integrations }: { integrations: readonly IntegrationStatus[] }) {
  const { setFallback, mock } = useLive()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const forced = integrations.filter((row) => row.forced)
  const flags = enabledFeatures()

  const run = async (jobs: readonly IntegrationStatus[], force: boolean) => {
    setBusy(true)
    setError(null)
    try {
      for (const job of jobs) await setFallback(job.name, force)
    } catch (reason) {
      setError(toApiError(reason).describe())
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="integrations-popover__head">
        <p className="integrations-popover__title">Live vs simulated</p>
        {forced.length > 0 ? (
          <button type="button" className="provider-clear" disabled={busy} onClick={() => void run(forced, false)}>
            Clear all
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="provider-error" role="alert">
          {error}
        </p>
      ) : null}
      {mock ? <p className="provider-note">Static demo: nothing is live, so no row can be forced.</p> : null}
      <ul className="integration-list provider-list">
        {integrations.map((status) => (
          <ProviderRow key={status.name} status={status} mock={mock} busy={busy} onSwitch={(row) => void run([row], !row.forced)} />
        ))}
      </ul>
      <p className="provider-flags">{flags.length > 0 ? `Flags on: ${flags.join(', ')}` : 'No feature flags on'}</p>
    </>
  )
}

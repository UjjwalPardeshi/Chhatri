/**
 * Loading and error states for every fetch (SPEC §20 "Resilience"). A server that cannot be
 * reached reads in plain words ("Can’t reach the Chhatri server …"), with the technical message
 * and code in the tooltip; every other error shows its message and code. Stale data stays on
 * screen through a network blip with a quiet note instead of a red banner.
 */
import type { ReactNode } from 'react'

import type { ApiError } from '../../api/client'

/** Errors that mean "the server is unreachable or slow", not "the request was wrong". */
const CONNECTION_CODES: ReadonlySet<string> = new Set(['NETWORK_ERROR', 'TIMEOUT'])

export function isConnectionError(error: ApiError): boolean {
  return CONNECTION_CODES.has(error.code)
}

/** The banner text for an error and whether its code is shown beside it. */
export function errorText(error: ApiError): { text: string; showCode: boolean } {
  if (error.code === 'NETWORK_ERROR') return { text: 'Can’t reach the Chhatri server. Check that it is running, then try again.', showCode: false }
  if (error.code === 'TIMEOUT') return { text: 'The Chhatri server is taking too long to answer. Try again in a moment.', showCode: false }
  return { text: error.describe(), showCode: true }
}

function ErrorLine({ error }: { error: ApiError }) {
  const { text, showCode } = errorText(error)
  return (
    <span title={showCode ? undefined : `${error.describe()} [${error.code}]`}>
      {text}
      {showCode ? (
        <>
          {' '}
          <span className="mono">[{error.code}]</span>
        </>
      ) : null}
    </span>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <output className="status-box" aria-live="polite">
      <span className="spinner" />
      <span>{label}</span>
    </output>
  )
}

type ErrorProps = { error: ApiError; title?: string; onRetry?: () => void }

export function ErrorState({ error, title = 'Could not load this', onRetry }: ErrorProps) {
  return (
    <div className="status-box status-box--error" role="alert">
      <span className="status-box__title">{title}</span>
      <span className="muted">
        <ErrorLine error={error} />
      </span>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

export function InlineError({ error, onDismiss }: { error: ApiError; onDismiss?: () => void }) {
  return (
    <div className="inline-error" role="alert">
      <ErrorLine error={error} />
      {onDismiss ? (
        <button type="button" className="btn btn--icon" aria-label="Dismiss" onClick={onDismiss}>
          ×
        </button>
      ) : null}
    </div>
  )
}

type AsyncViewProps<T> = {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
  label?: string
  children: (data: T) => ReactNode
}

/** A quiet line over stale content while the server is unreachable. */
function StaleNote({ onRetry }: { onRetry: () => void }) {
  return (
    <output className="stale-note">
      Showing the last data received · can’t reach the server right now.{' '}
      <button type="button" className="stale-note__retry" onClick={onRetry}>
        Try again
      </button>
    </output>
  )
}

/** Renders loading → error → content, keeping stale content visible while it reloads. */
export function AsyncView<T>({ data, error, loading, reload, label, children }: AsyncViewProps<T>) {
  if (data !== null) {
    const banner = error ? isConnectionError(error) ? <StaleNote onRetry={reload} /> : <InlineError error={error} onDismiss={reload} /> : null
    return (
      <>
        {banner}
        {children(data)}
      </>
    )
  }
  if (error) return <ErrorState error={error} onRetry={reload} />
  return loading ? <Loading label={label} /> : null
}

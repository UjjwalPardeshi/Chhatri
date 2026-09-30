/** Loading and error states for every fetch (SPEC §20 "Resilience"). */
import type { ReactNode } from 'react'

import type { ApiError } from '../../api/client'

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
        {error.describe()} <span className="mono">[{error.code}]</span>
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
      <span>
        {error.describe()} <span className="mono">[{error.code}]</span>
      </span>
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

/** Renders loading → error → content, keeping stale content visible while it reloads. */
export function AsyncView<T>({ data, error, loading, reload, label, children }: AsyncViewProps<T>) {
  if (data !== null) {
    return (
      <>
        {error ? <InlineError error={error} onDismiss={reload} /> : null}
        {children(data)}
      </>
    )
  }
  if (error) return <ErrorState error={error} onRetry={reload} />
  return loading ? <Loading label={label} /> : null
}

/**
 * The six shared states of fs-04 section 7. Every screen root carries `data-state` (loading, empty, error, offline or
 * ready); loading is skeleton blocks and `aria-busy`, empty is one sentence, error is a plain sentence with Retry and
 * the code in small text, offline keeps the last data under a banner and disables what needs the network, and SIMULATED
 * and FALLBACK are badges. `ResourceScreen` puts a resource into the right state for a screen in one place.
 */
import { WifiOff } from 'lucide-react'
import { useId, type ComponentProps, type ReactNode } from 'react'

import type { ApiError } from '../../api/client'
import type { CopyKey } from '../copy/en'
import type { Resource, ScreenState } from '../hooks/useResource'
import { t } from '../lib/copy'
import { formatDateTime } from '../lib/format'
import { Button } from '../ui/button'
import { Skeleton } from '../ui/skeleton'
import { useMiniapp } from './MiniappContext'


/** The root of a screen: its test id (`screen-<name>`) and its state. */
export function ScreenRoot({ name, state, children }: { name: string; state: ScreenState; children?: ReactNode }) {
  return (
    <section data-testid={`screen-${name}`} data-state={state} aria-busy={state === 'loading' ? true : undefined} className="flex flex-col gap-4 p-4">
      {children}
    </section>
  )
}

/** Blocks shaped like a heading and two cards, so nothing jumps when the data arrives. */
export function SkeletonBlocks() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-3">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-16 w-full" />
    </output>
  )
}

export function EmptyState({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div data-testid="app-empty" className="flex flex-col items-start gap-3 rounded-lg border bg-card p-4">
      <p className="text-md text-ink-2">{message}</p>
      {children}
    </div>
  )
}

function errorKey(error: ApiError): CopyKey {
  if (error.code === 'NETWORK_ERROR') return 'error.network'
  if (error.code === 'TIMEOUT') return 'error.timeout'
  return error.status === 404 || error.code === 'not_found' ? 'error.not_found' : 'error.generic'
}

const SHOWS_NO_CODE: ReadonlySet<string> = new Set(['NETWORK_ERROR', 'TIMEOUT'])

/** A plain sentence, the code in small text (a contract violation shows `contract_violation`), and Retry. */
export function ErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const { lang } = useMiniapp()
  return (
    <div data-testid="app-error" role="alert" className="flex flex-col items-start gap-2 rounded-lg border border-blocked/40 bg-blocked-soft p-4">
      <p className="text-md font-bold text-foreground">{t(errorKey(error), lang)}</p>
      {SHOWS_NO_CODE.has(error.code) ? null : <p className="text-xs text-ink-3">{t('error.code', lang, { code: error.code })}</p>}
      <Button data-testid="app-error-retry" variant="outline" onClick={onRetry}>
        {t('error.retry', lang)}
      </Button>
    </div>
  )
}

/** "Offline. Showing data from {time}." The time is the replay time of the last good load. */
export function OfflineBanner({ time }: { time: string | null }) {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-offline-banner" className="flex items-center gap-2 rounded-md bg-referred-soft px-3 py-2 text-xs text-referred-ink">
      <WifiOff className="size-4 shrink-0" aria-hidden="true" />
      <span>{t('offline.banner', lang, { time: formatDateTime(time, lang) })}</span>
    </output>
  )
}

export { ModeBadge } from '../components/ModeBadge'

/** A button that needs the network: disabled while offline, with the reason in plain words beside it. */
export function NetworkButton({ disabled, ...props }: ComponentProps<typeof Button>) {
  const { online, lang } = useMiniapp()
  const reasonId = useId()
  return (
    <>
      <Button {...props} disabled={disabled === true || !online} aria-describedby={online ? undefined : reasonId} />
      {online ? null : (
        <p id={reasonId} className="text-xs text-ink-3">
          {t('offline.blocked', lang)}
        </p>
      )}
    </>
  )
}

type ResourceScreenProps<T> = {
  name: string
  resource: Resource<T>
  /** Drawn in the empty state: an `EmptyState` with the next-best action. */
  empty?: ReactNode
  skeleton?: ReactNode
  children: (data: T) => ReactNode
}

/** One resource, one screen: skeleton, error with Retry, empty, offline with the last data, or the data itself. */
export function ResourceScreen<T>({ name, resource, empty, skeleton, children }: ResourceScreenProps<T>) {
  const { state, data, error, reload, loadedAt } = resource
  const blocks = skeleton ?? <SkeletonBlocks />
  if (state === 'error' && error) return <ScreenRoot name={name} state="error"><ErrorState error={error} onRetry={reload} /></ScreenRoot>
  if (state === 'loading') return <ScreenRoot name={name} state="loading">{blocks}</ScreenRoot>
  if (state === 'empty') return <ScreenRoot name={name} state="empty">{empty}</ScreenRoot>
  if (state === 'offline' && data === null && error) {
    // Nothing was ever loaded: a banner "showing data from -" over a skeleton is a dead end, so say it and offer Try again.
    return <ScreenRoot name={name} state="offline"><ErrorState error={error} onRetry={reload} /></ScreenRoot>
  }
  if (state === 'offline') {
    return (
      <ScreenRoot name={name} state="offline">
        <OfflineBanner time={loadedAt} />
        {data === null ? blocks : children(data)}
      </ScreenRoot>
    )
  }
  return <ScreenRoot name={name} state="ready">{data === null ? null : children(data)}</ScreenRoot>
}

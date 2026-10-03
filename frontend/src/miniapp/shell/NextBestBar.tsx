/**
 * The next-best bar (fs-04 section 12): one sentence and one button above the tab bar, `data-nba` set to the rule id.
 * The shell owns the slot and the registration; card 3.11 owns the rules. A screen calls `useNextBestAction` with the
 * action that applies, or null, and the bar is absent when there is none (no empty strip). The action button needs the network.
 */
import { useEffect } from 'react'

import { useLatest } from '../../state/useLatest'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { useMiniapp, type NextBestAction } from './MiniappContext'
import { NetworkButton } from './SharedStates'

/** Registers the action for as long as the screen is mounted. `onAction` may change every render; the other fields are compared by value. */
export function useNextBestAction(action: NextBestAction | null): void {
  const { setNba } = useMiniapp()
  const latest = useLatest(action?.onAction ?? null)
  const id = action?.id ?? null
  const label = action?.label ?? ''
  const actionLabel = action?.actionLabel ?? ''
  useEffect(() => {
    if (id === null) return undefined
    setNba({ id, label, actionLabel, onAction: () => latest.current?.() })
    return () => setNba(null)
  }, [id, label, actionLabel, latest, setNba])
}

export function NextBestBar() {
  const { nba, lang, embedded } = useMiniapp()
  if (!nba) return null
  return (
    <aside data-testid="app-nba" data-nba={nba.id} aria-label={t('app.nba', lang)} className={cn('flex shrink-0 flex-col border-t bg-card', embedded ? 'gap-2 px-3 py-3' : 'gap-2 px-4 py-3')}>
      <p className={cn('font-medium leading-snug text-foreground', embedded ? 'text-sm' : 'text-base')}>{nba.label}</p>
      <NetworkButton data-testid="app-nba-action" size="default" onClick={nba.onAction}>
        {nba.actionLabel}
      </NetworkButton>
    </aside>
  )
}

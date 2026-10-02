/**
 * The `W` presenter key (fs-08 12.3) opens or closes the what-if drawer, which lives in the /live page while the key
 * handler lives with the replay controls. A window event joins them without a shared provider: the key handler asks,
 * and the page that owns the drawer (only /live, only with the h24_whatif flag) answers.
 */
import { useEffect } from 'react'

import { useLatest } from './useLatest'

export const WHATIF_TOGGLE_EVENT = 'chhatri:whatif-toggle'

export function requestWhatIfToggle(): void {
  window.dispatchEvent(new Event(WHATIF_TOGGLE_EVENT))
}

/** Calls `handler` each time the W key (or anything else) asks to toggle the drawer; off while `enabled` is false. */
export function useWhatIfToggle(handler: () => void, enabled: boolean): void {
  const latest = useLatest(handler)
  useEffect(() => {
    if (!enabled) return undefined
    const onToggle = () => latest.current()
    window.addEventListener(WHATIF_TOGGLE_EVENT, onToggle)
    return () => window.removeEventListener(WHATIF_TOGGLE_EVENT, onToggle)
  }, [enabled, latest])
}

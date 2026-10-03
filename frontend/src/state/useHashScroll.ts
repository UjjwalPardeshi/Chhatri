/**
 * A deep link to a section (`/backtest#pricing`). The console scrolls inside `.app-main`, not the window, and a page's
 * sections render after their data arrives, so the browser's own jump to the hash finds nothing to scroll to. This
 * scrolls the element with `id` into view once per navigation, when `ready` says it and everything above it have
 * rendered, so the page does not move under it afterwards.
 */
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'

export function useHashScroll(id: string, ready: boolean): void {
  const { hash, key } = useLocation()
  /** The navigation already scrolled for, so a re-render or a reload of the data does not pull the page back. */
  const scrolledFor = useRef<string | null>(null)
  useEffect(() => {
    if (!ready || hash !== `#${id}` || scrolledFor.current === key) return
    scrolledFor.current = key
    document.getElementById(id)?.scrollIntoView({ block: 'start' })
  }, [hash, id, key, ready])
}

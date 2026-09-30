/**
 * Tracks a CSS media query (SPEC §20: the console works at 1280x720 and on phones). Components
 * that must change behaviour, not just style, at a breakpoint (the live map's framing) read it.
 * Environments without `matchMedia` (unit tests) report `false`.
 */
import { useSyncExternalStore } from 'react'

function mediaList(query: string): MediaQueryList | null {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
}

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = mediaList(query)
      list?.addEventListener('change', notify)
      return () => list?.removeEventListener('change', notify)
    },
    () => mediaList(query)?.matches ?? false,
    () => false,
  )
}

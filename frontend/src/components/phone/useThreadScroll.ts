/**
 * Where the chat thread scrolls (SPEC §20 "Merchant phone"): to the start of the latest moment,
 * the messages sent within a few minutes of the newest one (at 17:05: the rain message, the
 * ₹1,380 card and the paused instalment), so a burst reads from its first line. When the burst is
 * taller than the thread, the newest message wins. Live arrivals scroll smoothly, a page load
 * jumps.
 */
import { useEffect, useRef, type RefObject } from 'react'

/** Messages this close (simulated minutes) to the newest one belong to the same moment. */
export const BURST_MINUTES = 3
const MINUTE_MS = 60_000
/** Room left above the first message of the moment (px). */
const TOP_ROOM = 8
/** A moment that starts this close to the top shows from the top (the date chip stays in view). */
const SNAP_TOP_PX = 64

/** Scroll target for a thread: the top of the burst, or the bottom when the burst does not fit. */
export function burstScrollTop(rows: readonly { at: number; top: number }[], viewport: number, scrollHeight: number): number {
  const newest = Math.max(...rows.map((r) => r.at))
  if (rows.length === 0 || !Number.isFinite(newest)) return scrollHeight
  const first = rows.find((r) => r.at >= newest - BURST_MINUTES * MINUTE_MS)
  const raw = (first?.top ?? 0) - TOP_ROOM
  const top = raw < SNAP_TOP_PX ? 0 : raw
  return scrollHeight - top > viewport ? Math.max(0, scrollHeight - viewport) : top
}

function scrollToMoment(node: HTMLDivElement, behavior: ScrollBehavior): void {
  const rows = [...node.querySelectorAll<HTMLElement>('[data-at]')].map((el) => ({ at: Date.parse(el.dataset.at ?? ''), top: el.offsetTop }))
  const top = burstScrollTop(rows, node.clientHeight, node.scrollHeight)
  if (typeof node.scrollTo === 'function') node.scrollTo({ top, behavior })
}

/**
 * Follows the latest moment; a slip photo that finishes loading after it arrived grows the thread,
 * so an image load re-aims the scroll (images do not bubble `load`, hence the capture listener).
 */
export function useThreadScroll(threadRef: RefObject<HTMLDivElement | null>, lastId: string | undefined, enabled: boolean): void {
  const seen = useRef<string | undefined>(undefined)
  useEffect(() => {
    const node = threadRef.current
    if (!node || !enabled || lastId === undefined) return
    const live = seen.current !== undefined
    seen.current = lastId
    scrollToMoment(node, live ? 'smooth' : 'auto')
  }, [threadRef, lastId, enabled])
  useEffect(() => {
    const node = threadRef.current
    if (!node || !enabled) return undefined
    const onLoad = (event: Event) => {
      if (event.target instanceof HTMLImageElement) scrollToMoment(node, 'auto')
    }
    node.addEventListener('load', onLoad, true)
    return () => node.removeEventListener('load', onLoad, true)
  }, [threadRef, enabled])
}

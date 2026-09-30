/**
 * Small motion hooks for the live moments (SPEC §20 live map at 17:04): count a number up when it
 * changes, and mark which values just changed so the UI can flash them once. Both respect
 * prefers-reduced-motion (values jump, nothing animates) and never animate on first render.
 */
import { useEffect, useRef, useState } from 'react'

export const COUNT_UP_MS = 500
export const FLASH_MS = 1_400

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Ease-out cubic, 0..1 → 0..1. */
export function easeOut(t: number): number {
  return 1 - (1 - t) ** 3
}

/** Shows `target`; when it changes, counts from the previous value over `ms` (whole numbers). */
export function useCountUp(target: number, ms: number = COUNT_UP_MS): number {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = from.current
    from.current = target
    if (start === target || prefersReducedMotion() || typeof requestAnimationFrame !== 'function') {
      setShown(target)
      return undefined
    }
    let frame = 0
    const began = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - began) / ms)
      setShown(Math.round(start + (target - start) * easeOut(t)))
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(frame)
      setShown(target)
    }
  }, [target, ms])
  return shown
}

/** Keys whose value changed (or appeared) since the previous render, cleared after `ms`. */
export function useChangedKeys(values: Readonly<Record<string, string>>, ms: number = FLASH_MS): ReadonlySet<string> {
  const signature = JSON.stringify(values)
  const previous = useRef<Readonly<Record<string, string>> | null>(null)
  const [changed, setChanged] = useState<ReadonlySet<string>>(() => new Set())
  useEffect(() => {
    const before = previous.current
    const now = JSON.parse(signature) as Record<string, string>
    previous.current = now
    if (!before) return undefined
    const keys = Object.keys(now).filter((k) => before[k] !== now[k])
    if (keys.length === 0) return undefined
    setChanged(new Set(keys))
    const timer = setTimeout(() => setChanged(new Set()), ms)
    return () => clearTimeout(timer)
  }, [signature, ms])
  return changed
}

/**
 * A hero figure that counts up once when the page opens ("312", "4 min"), ending on the exact
 * golden value (SPEC §17.2). Screen readers and reduced-motion viewers get the final value only;
 * values that are not a plain number with a suffix are shown as they are.
 */
import { useEffect, useState } from 'react'

const DURATION_MS = 900
const NUMBER_WITH_SUFFIX = /^(\d+)(.*)$/

/** Splits "4 min" into 4 and " min" (null when the value does not start with digits). */
export function splitCount(value: string): { n: number; suffix: string } | null {
  const match = NUMBER_WITH_SUFFIX.exec(value)
  return match ? { n: Number(match[1]), suffix: match[2] } : null
}

function reducedMotion(): boolean {
  return typeof window === 'undefined' || typeof window.matchMedia !== 'function' || window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Ease-out cubic: fast at first, settling on the value. */
const easeOut = (t: number): number => 1 - (1 - t) ** 3

export function CountUp({ value }: { value: string }) {
  const parts = splitCount(value)
  const [shown, setShown] = useState(() => (parts && !reducedMotion() ? 0 : null))
  useEffect(() => {
    if (!parts || shown === null) return undefined
    const start = performance.now()
    let frame = requestAnimationFrame(function tick(now) {
      const t = Math.min(1, (now - start) / DURATION_MS)
      setShown(t >= 1 ? null : Math.round(parts.n * easeOut(t)))
      if (t < 1) frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- runs once, on mount
  if (!parts || shown === null) return <>{value}</>
  return (
    <>
      <span className="visually-hidden">{value}</span>
      <span aria-hidden="true">
        {shown}
        {parts.suffix}
      </span>
    </>
  )
}

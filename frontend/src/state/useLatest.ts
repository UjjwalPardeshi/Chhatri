/**
 * Latest-value ref for stable callbacks (SPEC §20 live UI: map and stream handlers must not be
 * re-created on every render). Written after each render; read only in effects and handlers.
 */
import { useLayoutEffect, useRef, type RefObject } from 'react'

export function useLatest<T>(value: T): RefObject<T> {
  const ref = useRef(value)
  useLayoutEffect(() => {
    ref.current = value
  })
  return ref
}

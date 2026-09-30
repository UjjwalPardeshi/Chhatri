/**
 * Collision-free zone labels on the static storm map (deck slide 6, SPEC §17.2 golden labels):
 * the live map's greedy placement (map/labelLayout.ts) run on the static frame. Each label keeps
 * the deck's direction when it can (Z3 west, Z7 east, Z12 south-east, Z9 north-east) and moves
 * away from the legend, the time chip, the north arrow, Anil's pin card, the rain pill and the
 * other labels when it cannot, never past the frame's inset. The first paint uses the deck
 * offsets in container units (StormMap), so the map reads correctly before measuring.
 */
import { useLayoutEffect, type RefObject } from 'react'

import { layoutLabels, type LayoutItem, type Rect } from '../map/labelLayout'
import { applyOffset } from '../map/labels'

function rectIn(el: Element, frame: DOMRect): Rect {
  const r = el.getBoundingClientRect()
  return { x: r.left - frame.left, y: r.top - frame.top, w: r.width, h: r.height }
}

/** Places every `.zone-anchor[data-label]` in `figure` around the `[data-obstacle]` boxes. */
export function placeStormLabels(figure: HTMLElement, prefer: Readonly<Record<string, number>>): void {
  const frame = figure.getBoundingClientRect()
  if (frame.width === 0 || frame.height === 0) return
  const anchors = [...figure.querySelectorAll<HTMLElement>('.zone-anchor[data-label]')]
  const items: LayoutItem[] = anchors.flatMap((el) => {
    const id = el.dataset.label ?? ''
    const box = el.querySelector<HTMLElement>('[data-box]')
    if (!box) return []
    const at = el.getBoundingClientRect()
    return [{ id, anchor: { x: at.left - frame.left, y: at.top - frame.top }, w: box.offsetWidth, h: box.offsetHeight, fixed: null, prefer: prefer[id] }]
  })
  const obstacles = [...figure.querySelectorAll('[data-obstacle]')].map((el) => rectIn(el, frame)).filter((r) => r.w > 0 && r.h > 0)
  const offsets = layoutLabels(items, { x: 0, y: 0, w: frame.width, h: frame.height }, obstacles)
  for (const el of anchors) {
    const offset = offsets.get(el.dataset.label ?? '')
    if (offset) applyOffset(el, offset.dx, offset.dy)
  }
}

/** Runs the placement after paint and again whenever the figure is resized. */
export function useStormLabels(ref: RefObject<HTMLElement | null>, prefer: Readonly<Record<string, number>>): void {
  useLayoutEffect(() => {
    const figure = ref.current
    if (!figure) return undefined
    const run = () => placeStormLabels(figure, prefer)
    run()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(run) : null
    observer?.observe(figure)
    return () => observer?.disconnect()
  }, [ref, prefer])
}

/**
 * Label placement for the live map (deck slide 6 style): each zone label tries a ring of offsets
 * around its zone anchor and takes the first that overlaps nothing placed before it (the merchant
 * pin and higher-priority labels go first). Offset labels get a leader line back to the anchor.
 */

export type Rect = { x: number; y: number; w: number; h: number }
export type Offset = { dx: number; dy: number }
export type LayoutItem = { id: string; anchor: { x: number; y: number }; w: number; h: number; fixed: Rect | null }

export const CANDIDATE_OFFSETS: readonly Offset[] = [
  { dx: 0, dy: 0 },
  { dx: 0, dy: -36 },
  { dx: 0, dy: 36 },
  { dx: -70, dy: -30 },
  { dx: 70, dy: 30 },
  { dx: -70, dy: 30 },
  { dx: 70, dy: -30 },
  { dx: 0, dy: -64 },
  { dx: 0, dy: 64 },
  { dx: -110, dy: 0 },
  { dx: 110, dy: 0 },
]
const GAP = 4

export function overlapArea(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + GAP
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + GAP
  return w > 0 && h > 0 ? w * h : 0
}

function rectAt(item: LayoutItem, offset: Offset): Rect {
  return { x: item.anchor.x + offset.dx - item.w / 2, y: item.anchor.y + offset.dy - item.h / 2, w: item.w, h: item.h }
}

function outside(rect: Rect, bounds: Rect): number {
  const dx = Math.max(0, bounds.x - rect.x) + Math.max(0, rect.x + rect.w - (bounds.x + bounds.w))
  const dy = Math.max(0, bounds.y - rect.y) + Math.max(0, rect.y + rect.h - (bounds.y + bounds.h))
  return (dx + dy) * rect.h
}

/** Greedy placement in the given (priority) order; returns an offset per movable item. */
export function layoutLabels(items: readonly LayoutItem[], bounds: Rect): Map<string, Offset> {
  const placed: Rect[] = items.flatMap((item) => (item.fixed ? [item.fixed] : []))
  const result = new Map<string, Offset>()
  for (const item of items) {
    if (item.fixed) continue
    let best: { offset: Offset; cost: number } | null = null
    for (const offset of CANDIDATE_OFFSETS) {
      const rect = rectAt(item, offset)
      const cost = placed.reduce((sum, other) => sum + overlapArea(rect, other), 0) + outside(rect, bounds)
      if (!best || cost < best.cost) best = { offset, cost }
      if (cost === 0) break
    }
    const chosen = best?.offset ?? CANDIDATE_OFFSETS[0]
    placed.push(rectAt(item, chosen))
    result.set(item.id, chosen)
  }
  return result
}

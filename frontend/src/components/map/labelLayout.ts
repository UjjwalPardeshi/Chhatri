/**
 * Label placement for the live map (deck slide 6 composition, SPEC §20 "zone labels"): every zone
 * label sits beside its zone on a short leader line, pushed outward from the middle of the storm
 * (so Z3 goes west, Z12 south and Z9 north-east, as on the deck), never over another label, the
 * merchant pin, the rain pill or a map overlay (legend, status chip), and never outside the map.
 *
 * Candidates are tried in order of how closely they follow the outward direction; the first one
 * that collides with nothing wins, otherwise the least-overlapping one. The chosen box is then
 * clamped inside the map with an inset, so a label can never be cut by the map edge.
 */

export type Rect = { x: number; y: number; w: number; h: number }
export type Offset = { dx: number; dy: number }
/**
 * One label: its anchor, its box size, a fixed box (pin, water names) or null when it may move,
 * and optionally the direction it prefers (radians, screen coordinates: -π/2 is up), used instead
 * of "outward from the storm" (the rain pill prefers to sit above the band).
 */
export type LayoutItem = { id: string; anchor: { x: number; y: number }; w: number; h: number; fixed: Rect | null; prefer?: number }

/** Minimum clearance kept between placed boxes (px). */
const GAP = 4
/** Labels stay at least this far inside the map edge (px). */
export const EDGE_INSET = 12
/** Leader-line lengths tried, shortest first (px between the anchor and the nearest box edge). */
export const LEADER_STEPS: readonly number[] = [16, 44, 76]
/** Directions tried around each anchor (every 30 degrees). */
const DIRECTIONS = 12
const TURN = Math.PI * 2

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

function angleGap(a: number, b: number): number {
  const d = Math.abs(a - b) % TURN
  return d > Math.PI ? TURN - d : d
}

/** Offset that puts the box's near edge `leader` px from the anchor in direction `angle`. */
export function offsetFor(item: Pick<LayoutItem, 'w' | 'h'>, angle: number, leader: number): Offset {
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  return { dx: Math.round(cos * (item.w / 2 + leader)), dy: Math.round(sin * (item.h / 2 + leader)) }
}

/** Candidate offsets for one label, most preferred first (outward from `centre`). */
export function candidateOffsets(item: LayoutItem, centre: { x: number; y: number } | null): Offset[] {
  const outward = centre ? Math.atan2(item.anchor.y - centre.y, item.anchor.x - centre.x) : -Math.PI / 2
  const still = centre !== null && Math.hypot(item.anchor.x - centre.x, item.anchor.y - centre.y) < 1
  const preferred = item.prefer ?? (still ? -Math.PI / 2 : outward)
  const angles = Array.from({ length: DIRECTIONS }, (_, i) => (i * TURN) / DIRECTIONS).toSorted((a, b) => angleGap(a, preferred) - angleGap(b, preferred))
  return LEADER_STEPS.flatMap((leader) => angles.map((angle) => offsetFor(item, angle, leader)))
}

/** Shifts `offset` so the box lies inside `bounds` inset by EDGE_INSET (when it fits at all). */
export function clampOffset(item: LayoutItem, offset: Offset, bounds: Rect): Offset {
  const rect = rectAt(item, offset)
  const minX = bounds.x + EDGE_INSET
  const minY = bounds.y + EDGE_INSET
  const maxX = bounds.x + bounds.w - EDGE_INSET - rect.w
  const maxY = bounds.y + bounds.h - EDGE_INSET - rect.h
  const x = maxX < minX ? rect.x : Math.min(Math.max(rect.x, minX), maxX)
  const y = maxY < minY ? rect.y : Math.min(Math.max(rect.y, minY), maxY)
  return { dx: offset.dx + (x - rect.x), dy: offset.dy + (y - rect.y) }
}

function centreOf(items: readonly LayoutItem[]): { x: number; y: number } | null {
  const movable = items.filter((i) => !i.fixed && i.prefer === undefined)
  if (movable.length === 0) return null
  return {
    x: movable.reduce((sum, i) => sum + i.anchor.x, 0) / movable.length,
    y: movable.reduce((sum, i) => sum + i.anchor.y, 0) / movable.length,
  }
}

function inset(bounds: Rect): Rect {
  return { x: bounds.x + EDGE_INSET, y: bounds.y + EDGE_INSET, w: bounds.w - 2 * EDGE_INSET, h: bounds.h - 2 * EDGE_INSET }
}

/**
 * Greedy placement in the given (priority) order; `obstacles` are boxes no label may cover (map
 * overlays). Returns an offset per movable item, relative to its anchor.
 */
export function layoutLabels(items: readonly LayoutItem[], bounds: Rect, obstacles: readonly Rect[] = []): Map<string, Offset> {
  const placed: Rect[] = [...obstacles, ...items.flatMap((item) => (item.fixed ? [item.fixed] : []))]
  const inner = inset(bounds)
  const centre = centreOf(items)
  const result = new Map<string, Offset>()
  for (const item of items) {
    if (item.fixed) continue
    let best: { offset: Offset; cost: number } | null = null
    for (const candidate of candidateOffsets(item, centre)) {
      const rect = rectAt(item, candidate)
      const cost = placed.reduce((sum, other) => sum + overlapArea(rect, other), 0) + outside(rect, inner)
      if (!best || cost < best.cost) best = { offset: candidate, cost }
      if (cost === 0) break
    }
    const chosen = clampOffset(item, best?.offset ?? { dx: 0, dy: 0 }, bounds)
    placed.push(rectAt(item, chosen))
    result.set(item.id, chosen)
  }
  return result
}

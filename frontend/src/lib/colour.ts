/**
 * Deck colour scale for "sales vs expected" (SPEC §20): 40 % red → 70 % amber → 100 %+ green.
 * Intermediate stops keep the ramp free of muddy mixes (deck slide 6 look); values outside
 * [40, 100] clamp to the end colours. Null (no data) is neutral grey.
 */

export type ColourStop = { pct: number; hex: string }

export const SCALE_RED = '#b91c1c'
export const SCALE_AMBER = '#e39a4f'
export const SCALE_GREEN = '#6dbb73'
export const NO_DATA_COLOUR = '#c7ced9'

export const COLOUR_STOPS: readonly ColourStop[] = Object.freeze([
  { pct: 40, hex: SCALE_RED },
  { pct: 55, hex: '#d6603a' },
  { pct: 70, hex: SCALE_AMBER },
  { pct: 85, hex: '#e7d38b' },
  { pct: 100, hex: SCALE_GREEN },
])

/** The area trigger floor (rules.yaml area.index_floor_pct, SPEC §8.2) drawn as the sparkline rule. */
export const INDEX_FLOOR_PCT = 50

/** The trigger floor shown in the legend: "Pays below 50% for 3 h, with alert" (SPEC §8.2, §20). */
export const LEGEND_RULE = `Pays below ${INDEX_FLOOR_PCT}% for 3 h, with alert`

function parseHex(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

function toHex(rgb: [number, number, number]): string {
  return `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')}`
}

function mix(a: string, b: string, t: number): string {
  const ca = parseHex(a)
  const cb = parseHex(b)
  return toHex([0, 1, 2].map((i) => ca[i] + (cb[i] - ca[i]) * t) as [number, number, number])
}

export function indexColour(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || !Number.isFinite(pct)) return NO_DATA_COLOUR
  const first = COLOUR_STOPS[0]
  const last = COLOUR_STOPS[COLOUR_STOPS.length - 1]
  if (pct <= first.pct) return first.hex
  if (pct >= last.pct) return last.hex
  const upper = COLOUR_STOPS.findIndex((stop) => stop.pct >= pct)
  const lo = COLOUR_STOPS[upper - 1]
  const hi = COLOUR_STOPS[upper]
  return mix(lo.hex, hi.hex, (pct - lo.pct) / (hi.pct - lo.pct))
}

/** CSS linear-gradient for the legend bar, same stops as the map. */
export function legendGradient(): string {
  const span = COLOUR_STOPS[COLOUR_STOPS.length - 1].pct - COLOUR_STOPS[0].pct
  const parts = COLOUR_STOPS.map((s) => `${s.hex} ${Math.round(((s.pct - COLOUR_STOPS[0].pct) / span) * 100)}%`)
  return `linear-gradient(90deg, ${parts.join(', ')})`
}

/**
 * Live feed grouping (SPEC §19.2 FeedItem, §20 "live event feed"): at 17:00 and 17:04/17:05 the
 * replay writes one line per zone for the same event (three triggers, three credits, three sets
 * of paused instalments). Same-minute, same-type lines about different zones fold into one row
 * (even when other types interleave within that minute),
 * "Loan instalments paused · Z3 56 · Z7 18 · Z12 50", so the feed shows the story, not a list.
 * Each part keeps the line's key figure (a rupee amount, a percentage or a leading count); the
 * full original lines stay available as the row's tooltip.
 */
import type { FeedItem } from '../../api/types'
import { INDEX_FLOOR_PCT } from '../../lib/colour'

/** Titles for the folded rows, by feed type (types without a title are never folded). */
export const GROUP_TITLES: Readonly<Record<string, string>> = Object.freeze({
  trigger: 'Area triggers fired',
  decision: 'Area payouts approved',
  payout: 'Area payouts credited',
  instalment: 'Loan instalments paused',
  watch: `Below ${INDEX_FLOOR_PCT}% of expected, alert active`,
})

/**
 * How a folded part reads, by feed type, so every figure carries its unit: "56 in Z3" (paused
 * instalments), "Z3 for 2 h" (hours below the floor), "Z3 at 38%" (trigger index). Other types
 * read "Z3 ₹1,79,820".
 */
export function partText(type: string, part: FeedPart): string {
  if (part.figure === null) return part.zone
  if (type === 'instalment') return `${part.figure} in ${part.zone}`
  if (type === 'watch') return `${part.zone} for ${part.figure}`
  if (type === 'trigger') return `${part.zone} at ${part.figure}`
  return `${part.zone} ${part.figure}`
}

/** Feed types that move money (shown with a green rule and a bold rupee value). */
export const MONEY_TYPES: ReadonlySet<string> = new Set(['payout', 'decision'])

export type FeedPart = { zone: string; figure: string | null }
export type FeedRow =
  | { kind: 'item'; key: string; at: string; type: string; text: string }
  | { kind: 'group'; key: string; at: string; type: string; title: string; parts: FeedPart[]; texts: string[] }

const RUPEES = /₹[\d,]+(?:\.\d+)?/
const PERCENT = /\d+%/
const LEADING_COUNT = /^\d[\d,]*(?=\s)/
const HOURS = /\d+ h\b/

/** Which figure a folded part keeps, by feed type (others: a percentage, a count, then rupees). */
const FIGURES: Readonly<Record<string, RegExp>> = Object.freeze({ payout: RUPEES, decision: RUPEES, instalment: LEADING_COUNT, watch: HOURS, trigger: PERCENT })

/** The figure worth keeping from one line (see FIGURES), or null when the line has none. */
export function keyFigure(type: string, text: string): string | null {
  const preferred = FIGURES[type]?.exec(text)?.[0]
  if (preferred) return preferred
  return PERCENT.exec(text)?.[0] ?? LEADING_COUNT.exec(text)?.[0] ?? RUPEES.exec(text)?.[0] ?? null
}

function minuteOf(at: string): string {
  return at.slice(0, 16)
}

function byZone(a: FeedItem, b: FeedItem): number {
  return (a.zone_id ?? '').localeCompare(b.zone_id ?? '', 'en', { numeric: true })
}

function toRow(bucket: readonly FeedItem[]): FeedRow {
  const first = bucket[0]
  const title = GROUP_TITLES[first.type]
  const zones = new Set(bucket.map((i) => i.zone_id))
  const foldable = bucket.length > 1 && title !== undefined && bucket.every((i) => i.zone_id) && zones.size === bucket.length
  if (!foldable) return { kind: 'item', key: `${first.id}-${first.at}`, at: first.at, type: first.type, text: first.text_en }
  const sorted = bucket.toSorted(byZone)
  return {
    kind: 'group',
    key: `g-${first.type}-${first.at}-${sorted.map((i) => i.id).join('.')}`,
    at: first.at,
    type: first.type,
    title,
    parts: sorted.map((i) => ({ zone: i.zone_id as string, figure: keyFigure(i.type, i.text_en) })),
    texts: sorted.map((i) => i.text_en),
  }
}

/** Splits items (newest first) into same-minute, same-type buckets, in order of appearance. */
function buckets(sorted: readonly FeedItem[]): FeedItem[][] {
  const out: FeedItem[][] = []
  const index = new Map<string, FeedItem[]>()
  for (const item of sorted) {
    const key = `${minuteOf(item.at)}|${item.type}`
    const bucket = index.get(key)
    if (bucket) bucket.push(item)
    else {
      const fresh = [item]
      index.set(key, fresh)
      out.push(fresh)
    }
  }
  return out
}

/** Newest first; same-minute, same-type lines about different zones are folded (module doc). */
export function feedRows(items: readonly FeedItem[]): FeedRow[] {
  const sorted = items.toSorted((a, b) => Date.parse(b.at) - Date.parse(a.at) || b.id - a.id)
  return buckets(sorted).flatMap((bucket) => {
    const row = toRow(bucket)
    return row.kind === 'group' || bucket.length === 1 ? [row] : bucket.map((i) => toRow([i]))
  })
}

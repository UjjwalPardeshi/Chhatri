/**
 * One-dimensional label placement for the replay scrubber's chapter ticks (content/chapters.ts).
 * Each label wants to sit centred over its tick; neighbours are pushed apart by a gap and the row
 * is kept inside the track. The 17:00, 17:04 and 17:05 ticks of the monsoon replay are one minute
 * apart, so their labels fan out sideways and a thin leader joins each label to its tick.
 */

export type ChapterBox = { x: number; w: number }

/** Minimum clearance between two labels (px). */
export const LABEL_GAP = 8

/**
 * Left edge of each label (px from the track start). `items` are sorted by `x`. A forward pass
 * pushes labels right past their left neighbour, a backward pass pulls them back inside `width`.
 * When the labels are wider than the track together they overlap at the left edge; the caller
 * can detect that with `labelsFit`.
 */
export function layoutChapters(items: readonly ChapterBox[], width: number, gap: number = LABEL_GAP): number[] {
  const lefts = items.map((item) => item.x - item.w / 2)
  for (let i = 0; i < lefts.length; i += 1) {
    const floor = i === 0 ? 0 : lefts[i - 1] + items[i - 1].w + gap
    lefts[i] = Math.max(lefts[i], floor)
  }
  for (let i = lefts.length - 1; i >= 0; i -= 1) {
    const ceiling = i === lefts.length - 1 ? width - items[i].w : lefts[i + 1] - gap - items[i].w
    lefts[i] = Math.max(0, Math.min(lefts[i], ceiling))
  }
  return lefts
}

/** Whether all labels fit side by side in `width`. */
export function labelsFit(items: readonly ChapterBox[], width: number, gap: number = LABEL_GAP): boolean {
  const total = items.reduce((sum, item) => sum + item.w, 0) + gap * Math.max(0, items.length - 1)
  return total <= width
}

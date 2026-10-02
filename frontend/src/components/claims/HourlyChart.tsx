/**
 * Expected vs actual sales by hour for a case (SPEC §12 evidence "expected vs actual"): grey
 * expected bars, blue actual bars with rounded tops, light gridlines (₹200/h, ₹400/h …) labelled
 * in a left gutter, a red zero tick for hours with no sales at all, and a labelled band over the
 * hours that fell below the trigger floor ("No payments" when every one of them was zero; "₹0"
 * or "<50%" when the band is narrow). Every bar has its numbers as a tooltip; the legend gives the
 * totals over the hours shown ("06:00–22:00 totals").
 */
import type { CaseEvidence } from '../../api/types'
import { INDEX_FLOOR_PCT } from '../../lib/colour'
import { formatInr } from '../../lib/money'
import { dayLabel, hhmm } from '../../lib/time'
import { nextHour } from '../panel/zoneTrend'

type Rows = NonNullable<CaseEvidence['expected_vs_actual']>

const CHART_HEIGHT = 120
const PCT = 100
/** Gridline steps in paise (₹100, ₹200, ₹500, ₹1,000 ...): the largest one under the tallest bar. */
const GRID_STEPS_PAISE: readonly number[] = [10_000, 20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000]

export type LowRun = { from: number; to: number; label: string }

function isLow(r: Rows[number], floorPct: number): boolean {
  return r.expected_paise > 0 && r.actual_paise * PCT < r.expected_paise * floorPct
}

/** The longest run of hours whose actual sales were below the floor share of expected. */
/** `floorPct` is the published policy floor (area.index_floor_pct); the constant only stands in until the policy has loaded. */
export function lowRun(rows: Rows, floorPct: number = INDEX_FLOOR_PCT): LowRun | null {
  let best: { from: number; to: number } | null = null
  let start = -1
  for (let i = 0; i <= rows.length; i += 1) {
    const low = i < rows.length && isLow(rows[i], floorPct)
    if (low && start === -1) start = i
    if (!low && start !== -1) {
      if (best === null || i - 1 - start > best.to - best.from) best = { from: start, to: i - 1 }
      start = -1
    }
  }
  if (best === null) return null
  const silent = rows.slice(best.from, best.to + 1).every((r) => r.actual_paise === 0)
  return { ...best, label: silent ? 'No payments' : `Below ${floorPct}% of expected` }
}

export function gridStep(max: number): number | null {
  return GRID_STEPS_PAISE.findLast((step) => step <= max) ?? null
}

/** Gridlines under the tallest bar: two or more when a step fits twice, else one (or none). */
export function gridLines(max: number): number[] {
  const step = gridStep(max / 2) ?? gridStep(max)
  if (step === null) return []
  return Array.from({ length: Math.floor(max / step) }, (_, i) => (i + 1) * step)
}

/** The band's tag when the band is too narrow for the words. */
export function shortRunLabel(run: LowRun, floorPct: number = INDEX_FLOOR_PCT): string {
  return run.label === 'No payments' ? '₹0' : `<${floorPct}%`
}

/** "06:00–22:00 totals" for rows from 06:00 to 21:00. */
export function totalsLabel(rows: Rows): string {
  const first = rows[0]?.hour
  const last = rows.at(-1)?.hour
  return first && last ? `${hhmm(first)}–${nextHour(hhmm(last))} totals` : 'totals'
}

export function HourlyChart({ rows, floorPct = INDEX_FLOOR_PCT }: { rows: Rows; floorPct?: number }) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.expected_paise, r.actual_paise)))
  const expected = rows.reduce((sum, r) => sum + r.expected_paise, 0)
  const actual = rows.reduce((sum, r) => sum + r.actual_paise, 0)
  const run = lowRun(rows, floorPct)
  const colPct = PCT / Math.max(1, rows.length)
  return (
    <figure className="ev-chart">
      <figcaption>
        <span>Expected vs actual sales by hour · {dayLabel(rows[0]?.hour)}</span>
        <span className="num">
          <span className="swatch swatch--expected" /> expected {formatInr(expected)} <span className="swatch swatch--actual" /> actual {formatInr(actual)}{' '}
          <span className="muted">({totalsLabel(rows)})</span>
        </span>
      </figcaption>
      <div className="ev-chart__area" style={{ height: CHART_HEIGHT }}>
        {run ? (
          <span className="ev-chart__band" style={{ left: `${run.from * colPct}%`, width: `${(run.to - run.from + 1) * colPct}%` }}>
            <span className="ev-chart__band-label" title={run.label}>
              <span className="ev-chart__band-long">{run.label}</span>
              <span className="ev-chart__band-short">{shortRunLabel(run, floorPct)}</span>
            </span>
          </span>
        ) : null}
        {gridLines(max).map((line) => (
          <span key={line} className="ev-chart__grid" style={{ bottom: `${(line / max) * PCT}%` }}>
            <span className="num">{formatInr(line)}/h</span>
          </span>
        ))}
        <div className="ev-chart__bars">
          {rows.map((r) => (
            <div key={r.hour} className="ev-chart__hour" title={`${hhmm(r.hour)} · expected ${formatInr(r.expected_paise)} · actual ${formatInr(r.actual_paise)}`}>
              <span className="ev-chart__plot">
                <span className="ev-chart__expected" style={{ height: `${(r.expected_paise / max) * PCT}%` }} />
                <span className="ev-chart__actual" style={{ height: `${(r.actual_paise / max) * PCT}%` }} />
                {r.actual_paise === 0 && r.expected_paise > 0 ? <span className="ev-chart__zero" /> : null}
              </span>
              <span className="ev-chart__label num">{hhmm(r.hour).slice(0, 2)}</span>
            </div>
          ))}
        </div>
      </div>
    </figure>
  )
}

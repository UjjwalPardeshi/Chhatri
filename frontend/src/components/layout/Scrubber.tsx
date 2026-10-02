/**
 * Replay scrubber (SPEC §17.1 clock, §17.2 story moments): a 6 px track under the replay controls
 * from the scenario start to its end, the elapsed part in blue with a knob at the simulated now,
 * and the scenario's chapters (content/chapters.ts) as labelled ticks. Picking a chapter seeks a
 * minute before it, so the moment happens live on the next Play. Labels that would collide fan
 * out sideways (chapterLayout.ts) and an elbow leader joins each to its tick.
 */
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

import type { ClockState } from '../../api/types'
import { CHAPTERS, minuteBefore, minuteOfDay, type Chapter } from '../../content/chapters'
import { hhmm } from '../../lib/time'
import { layoutChapters } from './chapterLayout'

const PCT = 100
/** Vertical geometry of the leader row (px): track bottom → label top. */
const LEADER_H = 7
const LEADER_MID = 3.5

/** Position of an HH:MM chapter on the track, in % of the scenario span (null outside it). */
export function chapterPct(clock: Pick<ClockState, 'start' | 'end'>, at: string): number | null {
  const start = minuteOfDay(hhmm(clock.start))
  const end = minuteOfDay(hhmm(clock.end))
  const minute = minuteOfDay(at)
  if (start === null || end === null || minute === null || end <= start) return null
  if (minute < start || minute > end) return null
  return ((minute - start) / (end - start)) * PCT
}

type Placed = { chapter: Chapter; pct: number; passed: boolean }

function placedChapters(clock: ClockState): Placed[] {
  const now = minuteOfDay(hhmm(clock.now)) ?? 0
  const chapters = clock.scenario ? CHAPTERS[clock.scenario] : []
  return chapters.flatMap((chapter) => {
    const pct = chapterPct(clock, chapter.at)
    return pct === null ? [] : [{ chapter, pct, passed: now >= (minuteOfDay(chapter.at) ?? 0) }]
  })
}

/** The scenario's chapters that sit on the track, left to right: what the scrubber labels and what keys 1 to 4 jump to. */
export function chaptersOnTrack(clock: ClockState): Chapter[] {
  return placedChapters(clock).map((placed) => placed.chapter)
}

/** Measured label positions (px) for the current chapters and track width. */
function useLabelLefts(chapters: readonly Placed[]) {
  const areaRef = useRef<HTMLDivElement>(null)
  const labelRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [layout, setLayout] = useState<{ key: string; width: number; lefts: number[]; widths: number[] } | null>(null)
  const key = chapters.map((c) => `${c.chapter.at}@${c.pct.toFixed(3)}`).join('|')
  useLayoutEffect(() => {
    const area = areaRef.current
    if (!area) return undefined
    const measure = () => {
      const width = area.clientWidth
      const widths = labelRefs.current.slice(0, chapters.length).map((el) => el?.offsetWidth ?? 0)
      const lefts = layoutChapters(
        chapters.map((c, i) => ({ x: (c.pct / PCT) * width, w: widths[i] })),
        width,
      )
      setLayout({ key, width, lefts, widths })
    }
    measure()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    observer?.observe(area)
    return () => observer?.disconnect()
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps -- `key` stands for `chapters`
  return { areaRef, labelRefs, layout: layout?.key === key && layout.width > 0 ? layout : null }
}

function Leaders({ chapters, layout }: { chapters: readonly Placed[]; layout: { width: number; lefts: number[]; widths: number[] } }) {
  return (
    <svg className="scrubber__leaders" width={layout.width} height={LEADER_H} aria-hidden="true" focusable="false">
      {chapters.map((c, i) => {
        const tick = (c.pct / PCT) * layout.width
        const label = layout.lefts[i] + layout.widths[i] / 2
        return <path key={c.chapter.at} data-passed={c.passed} d={`M${tick} 0V${LEADER_MID}H${label}V${LEADER_H}`} />
      })}
    </svg>
  )
}

type Props = { clock: ClockState; busy: boolean; onSeek: (hhmm: string) => void; extra?: ReactNode }

export function Scrubber({ clock, busy, onSeek, extra = null }: Props) {
  const chapters = placedChapters(clock)
  const { areaRef, labelRefs, layout } = useLabelLefts(chapters)
  const start = minuteOfDay(hhmm(clock.start)) ?? 0
  const end = minuteOfDay(hhmm(clock.end)) ?? 0
  const now = minuteOfDay(hhmm(clock.now)) ?? start
  const pct = end > start ? Math.min(PCT, Math.max(0, ((now - start) / (end - start)) * PCT)) : 0
  return (
    <fieldset className="scrubber" data-running={clock.running}>
      <legend className="visually-hidden">Replay timeline</legend>
      <span className="scrubber__edge num">{hhmm(clock.start)}</span>
      <div className="scrubber__area" ref={areaRef}>
        <progress className="visually-hidden" max={PCT} value={Math.round(pct)} aria-label={`Replay at ${hhmm(clock.now)}, ${hhmm(clock.start)} to ${hhmm(clock.end)}`} />
        <div className="scrubber__track" aria-hidden="true">
          <span className="scrubber__fill" style={{ transform: `scaleX(${pct / PCT})` }} />
          {chapters.map((c) => (
            <span key={c.chapter.at} className="scrubber__tick" data-passed={c.passed} style={{ left: `${c.pct}%` }} />
          ))}
          <span className="scrubber__knob-rail" style={{ transform: `translateX(${pct}%)` }}>
            <span className="scrubber__knob" />
          </span>
        </div>
        {layout ? <Leaders chapters={chapters} layout={layout} /> : null}
        <div className="scrubber__labels">
          {chapters.map((c, i) => (
            <button
              key={c.chapter.at}
              ref={(el) => {
                labelRefs.current[i] = el
              }}
              type="button"
              className="scrubber__chapter"
              data-passed={c.passed}
              disabled={busy}
              title={`Jump to ${minuteBefore(c.chapter.at)}, a minute before ${c.chapter.label.toLowerCase()}`}
              style={layout ? { left: `${layout.lefts[i]}px` } : { left: `${c.pct}%`, transform: 'translateX(-50%)' }}
              onClick={() => onSeek(minuteBefore(c.chapter.at))}
            >
              <span className="scrubber__at num">{c.chapter.at}</span> {c.chapter.label}
            </button>
          ))}
        </div>
      </div>
      <span className="scrubber__edge num">{hhmm(clock.end)}</span>
      {extra}
    </fieldset>
  )
}

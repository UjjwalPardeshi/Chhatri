/**
 * Live event feed (SPEC §20): newest first on simulated time. Same-minute lines about several
 * zones fold into one row (feedGroups.ts) whose figures carry their units ("56 in Z3"); money rows
 * carry a green rule and bold rupee values; the list fades out at the bottom and says how many
 * older events are below the fold. The header's "streaming" mark follows the live stream (SPEC
 * §20 "Resilience"): amber "reconnecting" while it is down, like the header pill.
 */
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'

import type { StreamStatus } from '../../api/stream'
import type { FeedItem } from '../../api/types'
import { hhmm } from '../../lib/time'
import { useLive } from '../../state/live'
import { feedRows, MONEY_TYPES, partText, type FeedRow } from './feedGroups'

const RUPEE_SPLIT = /(₹[\d,]+(?:\.\d+)?)/

/** Wraps rupee amounts in <strong> so money reads first. */
export function emphasiseRupees(text: string): ReactNode[] {
  return text.split(RUPEE_SPLIT).map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part))
}

/** Rows whose top edge is below the visible part of the list. */
function useHiddenCount(listRef: RefObject<HTMLOListElement | null>, signature: string): number {
  const [hidden, setHidden] = useState(0)
  useEffect(() => {
    const list = listRef.current
    if (!list) return undefined
    const measure = () => {
      const bottom = list.scrollTop + list.clientHeight
      setHidden([...list.children].filter((row) => (row as HTMLElement).offsetTop >= bottom - 4).length)
    }
    measure()
    list.addEventListener('scroll', measure, { passive: true })
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    observer?.observe(list)
    return () => {
      list.removeEventListener('scroll', measure)
      observer?.disconnect()
    }
  }, [listRef, signature])
  return hidden
}

function Row({ row }: { row: FeedRow }) {
  const money = MONEY_TYPES.has(row.type)
  return (
    <li className={`feed__item ${money ? 'feed__item--money' : ''}`} data-type={row.type} title={row.kind === 'group' ? row.texts.join('\n') : undefined}>
      <time className="feed__time num">{hhmm(row.at)}</time>
      <span className="feed__dot" />
      {row.kind === 'group' ? (
        <span className="feed__text">
          <span className="feed__title">{row.title}</span>
          <span className="feed__parts num">
            {row.parts.map((p) => (
              <span key={p.zone} className="feed__part">
                {money ? emphasiseRupees(partText(row.type, p)) : partText(row.type, p)}
              </span>
            ))}
          </span>
        </span>
      ) : (
        <span className="feed__text">{money ? emphasiseRupees(row.text) : row.text}</span>
      )}
    </li>
  )
}

/** The feed header's stream mark: "streaming" while events flow, "reconnecting" while they don't. */
export function streamMark(stream: StreamStatus): { text: string; tone: 'live' | 'down' } {
  return stream === 'open' ? { text: 'streaming', tone: 'live' } : { text: 'reconnecting', tone: 'down' }
}

export function EventFeed({ items, floorPct }: { items: readonly FeedItem[]; floorPct?: number }) {
  const { stream } = useLive()
  const rows = feedRows(items, floorPct)
  const listRef = useRef<HTMLOListElement>(null)
  const hidden = useHiddenCount(listRef, rows.map((r) => r.key).join('|'))
  const mark = streamMark(stream)
  return (
    <section className="card feed" aria-label="Live events">
      <header className="feed__head">
        <span className="eyebrow">Live events</span>
        <span className="feed__live" data-tone={mark.tone}>
          <span className="feed__live-dot" /> {mark.text}
        </span>
      </header>
      {rows.length === 0 ? (
        <p className="feed__empty muted">Nothing yet. Press play or seek to a time.</p>
      ) : (
        <div className={`feed__body ${hidden > 0 ? 'feed__body--more' : ''}`}>
          <ol className="feed__list" ref={listRef}>
            {rows.map((row) => (
              <Row key={row.key} row={row} />
            ))}
          </ol>
          {hidden > 0 ? <span className="feed__more num">{hidden === 1 ? '1 earlier event' : `${hidden} earlier events`}</span> : null}
        </div>
      )}
    </section>
  )
}

/** Live event feed (SPEC §20): newest first, simulated time, typed dot. */
import type { FeedItem } from '../../api/types'
import { hhmm } from '../../lib/time'

export function EventFeed({ items }: { items: readonly FeedItem[] }) {
  const sorted = items.toSorted((a, b) => Date.parse(b.at) - Date.parse(a.at) || b.id - a.id)
  return (
    <section className="card feed" aria-label="Live events">
      <header className="feed__head">
        <span className="eyebrow">Live events</span>
        <span className="feed__live">
          <span className="feed__live-dot" /> streaming
        </span>
      </header>
      {sorted.length === 0 ? (
        <p className="feed__empty muted">Nothing yet. Press play or seek to a time.</p>
      ) : (
        <ol className="feed__list">
          {sorted.map((item) => (
            <li key={`${item.id}-${item.at}`} className="feed__item" data-type={item.type}>
              <time className="feed__time num">{hhmm(item.at)}</time>
              <span className="feed__dot" />
              <span className="feed__text">{item.text_en}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/** Turns https:// URLs in message text into links (Paytm premium link, SPEC §13.4 COVER_LINK). */
import type { ReactNode } from 'react'

const URL_PATTERN = /(https:\/\/[^\s]+)/g

export function linkify(text: string): ReactNode[] {
  return text.split(URL_PATTERN).map((part, i) =>
    i % 2 === 1 ? (
      <a key={i} href={part} target="_blank" rel="noreferrer noopener" className="bubble__link">
        {part}
      </a>
    ) : (
      part
    ),
  )
}

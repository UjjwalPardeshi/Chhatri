/** Phone frame (deck slides 1 and 7): status bar, "Paytm · Chhatri" header, chat, Soundbox, composer. */
import { useRef, type ReactNode } from 'react'

import type { Message } from '../../api/types'
import { hhmm, weekdayDayLabel } from '../../lib/time'
import { MessageBubble } from './Bubbles'
import { useThreadScroll } from './useThreadScroll'

type Props = {
  now: string
  messages: readonly Message[]
  footer: ReactNode
  status: ReactNode
  testId?: string
  /** Follow new messages (live chat, see useThreadScroll); story phones stay anchored at the top. */
  autoScroll?: boolean
}

export function Phone({ now, messages, footer, status, testId = 'phone', autoScroll = true }: Props) {
  const threadRef = useRef<HTMLDivElement>(null)
  useThreadScroll(threadRef, messages.at(-1)?.id, autoScroll)
  return (
    <div className="phone" data-testid={testId}>
      <div className="phone__status num">
        <span>{hhmm(now)}</span>
        <span>4G · 58%</span>
      </div>
      <header className="phone__header">
        <span className="phone__avatar">C</span>
        <div>
          <p className="phone__name">Paytm · Chhatri</p>
          <p className="phone__sub">Merchant protection · Hindi, English</p>
        </div>
      </header>
      {/* The day sits in its own strip above the thread, so it never covers a bubble (WhatsApp keeps it in view too). */}
      <div className="phone__day">
        <span className="day-chip">{weekdayDayLabel(now)}</span>
      </div>
      <div className="phone__thread" ref={threadRef} aria-live="polite">
        {status}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
      {footer}
    </div>
  )
}

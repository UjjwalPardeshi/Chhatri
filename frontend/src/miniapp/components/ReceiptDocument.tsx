/**
 * The frame of the receipt (fs-04 S7, design system 5.2): one card holding a description list, so a screen reader
 * hears each label with its value and the printed page reads as a form. A row does not split across printed pages.
 * `ReceiptNotice` is the line at the top (SIMULATED, or "no receipt yet" for a record). The document has no
 * behaviour: the screen decides which rows there are, from what the receipt holds, and what leads them.
 */
import type { ReactNode } from 'react'

import { cn } from '../lib/cn'

/** `lead` is drawn between the heading and the rows, across the whole width (who authorised the money). */
type DocumentProps = { heading: ReactNode; lead?: ReactNode; children: ReactNode }

export function ReceiptDocument({ heading, lead, children }: DocumentProps) {
  return (
    <article data-testid="receipt-document" className="flex flex-col gap-4 rounded-lg border bg-card p-4">
      {heading}
      {lead}
      <dl className="flex flex-col divide-y">{children}</dl>
    </article>
  )
}

type RowProps = { label: ReactNode; testId?: string; className?: string; children: ReactNode }

export function ReceiptRow({ label, testId, className, children }: RowProps) {
  return (
    <div data-testid={testId} className={cn('flex flex-col gap-1.5 py-3 break-inside-avoid first:pt-0 last:pb-0', className)}>
      <dt className="text-caption font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  )
}

export function ReceiptNotice({ testId, tone, children }: { testId: string; tone: 'demo' | 'neutral'; children: ReactNode }) {
  return (
    <p data-testid={testId} className={cn('rounded-lg px-3 py-2 text-caption', tone === 'demo' ? 'bg-demo-soft text-demo' : 'bg-secondary text-ink-2')}>
      {children}
    </p>
  )
}

/**
 * A status as a coloured word with a small dot (design system 11.2): restrained colour plus the plain label, never
 * colour alone. `data-status` carries the engine's own word for the tests and the receipt.
 */
import type { ComponentProps } from 'react'

import { cn } from '../lib/cn'

export type StatusTone = 'paid' | 'decided' | 'referred' | 'blocked' | 'neutral'

const TEXT: Readonly<Record<StatusTone, string>> = {
  paid: 'text-paid-ink',
  decided: 'text-decided',
  referred: 'text-referred-ink',
  blocked: 'text-blocked',
  neutral: 'text-ink-3',
}

export function StatusWord({ tone, className, children, ...props }: { tone: StatusTone } & ComponentProps<'span'>) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-bold', TEXT[tone], className)} {...props}>
      <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-current" />
      {children}
    </span>
  )
}

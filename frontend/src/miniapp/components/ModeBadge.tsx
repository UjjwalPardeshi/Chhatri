/**
 * The mode of a source or an action (design system 11.1, ADR 0004): an icon and the word, never colour alone. The word
 * is LIVE, SIMULATED or FALLBACK in capitals, written as such in the source and never translated. The mode comes from the
 * data; nothing here decides it. The app bar carries one summary badge, a receipt one per source, the alert banner and
 * the payment link their own.
 */
import { CircleDashed, CircleDot, TriangleAlert, type LucideIcon } from 'lucide-react'

import { cn } from '../lib/cn'
import { Badge } from '../ui/badge'

export type Mode = 'SIMULATED' | 'FALLBACK' | 'LIVE'

const ICON: Readonly<Record<Mode, LucideIcon>> = { LIVE: CircleDot, SIMULATED: CircleDashed, FALLBACK: TriangleAlert }

const STYLE: Readonly<Record<Mode, string>> = {
  SIMULATED: 'bg-demo-soft text-demo',
  FALLBACK: 'bg-fallback-soft text-fallback',
  LIVE: 'bg-live-soft text-live-ink',
}

export function ModeBadge({ mode, testId = 'app-mode-badge', className }: { mode: Mode; testId?: string; className?: string }) {
  const Icon = ICON[mode]
  return (
    <Badge variant="secondary" data-testid={testId} data-mode={mode} className={cn('tracking-wide', STYLE[mode], className)}>
      <Icon aria-hidden="true" />
      {mode}
    </Badge>
  )
}

/**
 * A banner with an icon, a title and words (design system 5.2, built on the generated `alert`): information
 * (`role="status"`), a warning such as a weather alert in force (also a status) or an error (`role="alert"`). The tone
 * is a soft tint with its ink, and the icon sits beside words, so colour never carries the message alone.
 */
import { CircleAlert, Info, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../lib/cn'
import { Alert, AlertDescription, AlertTitle } from '../ui/alert'

export type AlertTone = 'info' | 'warning' | 'error'

const TONE: Readonly<Record<AlertTone, { box: string; icon: LucideIcon }>> = {
  info: { box: 'border-decided/30 bg-decided-soft text-foreground', icon: Info },
  warning: { box: 'border-referred/40 bg-referred-soft text-referred-ink', icon: CircleAlert },
  error: { box: 'border-blocked/30 bg-blocked-soft text-blocked', icon: CircleAlert },
}

type AlertBannerProps = {
  tone?: AlertTone
  icon?: LucideIcon
  title: ReactNode
  /** Drawn at the end of the title row: a mode badge, for instance. */
  badge?: ReactNode
  children?: ReactNode
  testId?: string
  className?: string
}

export function AlertBanner({ tone = 'info', icon, title, badge, children, testId, className }: AlertBannerProps) {
  const { box, icon: toneIcon } = TONE[tone]
  const Icon = icon ?? toneIcon
  return (
    <Alert
      data-testid={testId}
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('items-start gap-y-1 px-3 py-3 has-[>svg]:grid-cols-[calc(var(--spacing)*5)_1fr] [&>svg]:size-5', box, className)}
    >
      <Icon aria-hidden="true" />
      <AlertTitle className="line-clamp-none flex min-h-0 flex-wrap items-center justify-between gap-x-2 gap-y-1 text-sm font-semibold tracking-normal">
        <span>{title}</span>
        {badge}
      </AlertTitle>
      {children ? <AlertDescription className="gap-1 text-sm text-current">{children}</AlertDescription> : null}
    </Alert>
  )
}

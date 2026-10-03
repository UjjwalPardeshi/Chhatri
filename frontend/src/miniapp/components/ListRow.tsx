/**
 * The list rows of a payments app: one white sheet with hairline dividers, each row a title, an optional second
 * line and a trailing value or chevron. Menus (Help, the Home shortcuts) use these instead of a card per row.
 */
import { ChevronRight } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { Link } from 'react-router'

import { cn } from '../lib/cn'

export function ListGroup({ as: Tag = 'div', className, ...props }: ComponentProps<'div'> & { as?: 'div' | 'nav' }) {
  return <Tag className={cn('flex flex-col overflow-hidden rounded-lg border bg-card [&>*+*]:border-t [&>*+*]:border-line-soft', className)} {...props} />
}

const ROW = 'flex min-h-14 items-center justify-between gap-3 px-4 py-3 outline-none hover:bg-paper-2 focus-visible:bg-paper-2 focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/50 active:bg-paper-2'

type ListRowLinkProps = { to: string; title: ReactNode; secondary?: ReactNode; trailing?: ReactNode } & Omit<ComponentProps<typeof Link>, 'to' | 'title'>

export function ListRowLink({ to, title, secondary, trailing, className, ...props }: ListRowLinkProps) {
  return (
    <Link to={to} className={cn(ROW, className)} {...props}>
      <span className="flex min-w-0 flex-col">
        <span className="text-md font-medium leading-snug text-foreground">{title}</span>
        {secondary ? <span className="text-caption leading-snug text-muted-foreground">{secondary}</span> : null}
      </span>
      <span className="flex shrink-0 items-center gap-1">
        {trailing}
        <ChevronRight className="size-5 text-faint" aria-hidden="true" />
      </span>
    </Link>
  )
}

/** A small caption above a group of rows. */
export function SectionLabel({ as: Tag = 'h3', className, ...props }: ComponentProps<'h3'> & { as?: 'h2' | 'h3' }) {
  return <Tag className={cn('px-1 text-caption font-bold text-ink-2', className)} {...props} />
}

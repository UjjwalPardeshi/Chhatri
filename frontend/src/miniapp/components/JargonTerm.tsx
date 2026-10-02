/**
 * A term of the jargon lens (H20): a button styled as underlined text (underline and colour, never colour alone) that
 * opens the sheet of its explanation. `term-<id>`, `aria-haspopup="dialog"`, a 44 px hit area through `min-h-11`. The
 * Sheet root and its trigger live here, so focus returns to this button when the sheet closes.
 */
import type { ReactNode } from 'react'

import { termKey, type TermId } from '../glossary'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { useMiniapp } from '../shell/MiniappContext'
import { Sheet, SheetTrigger } from '../ui/sheet'
import { JargonSheet } from './JargonSheet'

export function JargonTerm({ id, children, className }: { id: TermId; children?: ReactNode; className?: string }) {
  const { lang } = useMiniapp()
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button
          type="button"
          data-testid={`term-${id}`}
          aria-haspopup="dialog"
          className={cn(
            'inline-flex min-h-11 items-center rounded-sm px-1 text-sm font-medium text-primary underline underline-offset-4 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
            className,
          )}
        >
          {children ?? t(termKey(id, 'term'), lang)}
        </button>
      </SheetTrigger>
      <JargonSheet id={id} />
    </Sheet>
  )
}

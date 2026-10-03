/**
 * The clause chips of an answer (H17, screens 5.2): "From the policy: C4.1 C2". Every id was validated by the server
 * against the clause table, and a chip opens a bottom sheet with the id, the clause title in the app's words and the
 * server's own English title. A chip never shows text the model wrote.
 */
import { BookOpen } from 'lucide-react'
import { useRef } from 'react'

import type { AskClause } from '../api/ask'
import { clauseTitle } from '../components/SourceBadge'
import { ta } from '../copy/ask'
import { t } from '../lib/copy'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet'

const CHIP =
  'relative inline-flex min-h-6 max-w-full items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1 text-left text-xs font-medium text-ink-2 outline-none after:absolute after:inset-x-0 after:-inset-y-2.5 after:content-[""] focus-visible:ring-[3px] focus-visible:ring-ring/50'

function ClauseChip({ clause, lang }: { clause: AskClause; lang: Lang }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const title = clauseTitle(clause.id, lang) ?? clause.title
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button type="button" data-testid="ask-clause" data-clause={clause.id} aria-haspopup="dialog" className={CHIP}>
          <BookOpen className="size-3.5 shrink-0 text-link" aria-hidden="true" />
          <span className="num">{clause.id}</span>
          <span className="text-ink-3">{title}</span>
        </button>
      </SheetTrigger>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        data-testid="ask-clause-sheet"
        className="max-h-[85%] gap-0 overflow-y-auto rounded-t-2xl pb-2"
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          closeRef.current?.focus()
        }}
      >
        <SheetHeader className="gap-0.5 px-4 pt-5 pb-3">
          <SheetTitle className="text-xl font-medium">{title}</SheetTitle>
          <SheetDescription className="text-caption">
            <span className="num">{clause.id}</span> · <span lang="en">{clause.title}</span>
          </SheetDescription>
        </SheetHeader>
        <div className="border-t px-4 py-3">
          <SheetClose asChild>
            <Button ref={closeRef} data-testid="ask-clause-close" variant="outline" size="lg" className="w-full">
              {t('source.close', lang)}
            </Button>
          </SheetClose>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function AskClauses({ clauses, lang }: { clauses: readonly AskClause[]; lang: Lang }) {
  if (clauses.length === 0) return null
  const [label] = ta('ask.cites.policy', lang, { clauses: '\u0000' }).split('\u0000')
  return (
    <div data-testid="ask-clauses" className="flex flex-col gap-1.5">
      <p className="text-xs font-medium text-ink-3">{label.trim()}</p>
      <div className="flex flex-wrap gap-x-2 gap-y-5">
        {clauses.map((clause) => (
          <ClauseChip key={clause.id} clause={clause} lang={lang} />
        ))}
      </div>
    </div>
  )
}

/**
 * The jargon lens sheet (H20, fs-04 section 11): a bottom Sheet inside the phone frame that names a term in both
 * languages, says it in plain words and gives one example. Focus moves to Close when it opens, stays inside while it is
 * open (Radix traps it), and Esc or Close hands it back to the term that opened it (that is the trigger of the same
 * Radix root, see JargonTerm). The numbers in the words come from the rules; until they arrive the sheet holds the
 * place with skeleton lines, and a failure says so with Retry, so a raw `{placeholder}` is never shown.
 */
import { useRef } from 'react'

import { useRules } from '../hooks/useRules'
import { otherLanguage, termText, type TermId } from '../glossary'
import { t, translate } from '../lib/copy'
import { rulesParams } from '../lib/copyRules'
import { useMiniapp } from '../shell/MiniappContext'
import { ErrorState } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { SheetClose, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet'
import { Skeleton } from '../ui/skeleton'

function Placeholder() {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

function Body({ id }: { id: TermId }) {
  const { lang } = useMiniapp()
  const rules = useRules()
  if (rules.error && rules.data === null) return <ErrorState error={rules.error} onRetry={rules.reload} />
  if (rules.data === null) return <Placeholder />
  const { what, example } = termText(id, lang, rulesParams(rules.data))
  return (
    <>
      <section className="flex flex-col gap-1">
        <h3 className="text-xs font-medium text-muted-foreground">{t('lens.plain', lang)}</h3>
        <p lang={what.fallback ? what.lang : undefined} className="text-md">
          {what.text}
        </p>
      </section>
      <section data-testid="jargon-sheet-example" className="flex flex-col gap-1 rounded-lg bg-secondary p-3">
        <h3 className="text-xs font-medium text-muted-foreground">{t('lens.example', lang)}</h3>
        <p lang={example.fallback ? example.lang : undefined} className="text-sm text-secondary-foreground">
          {example.text}
        </p>
      </section>
    </>
  )
}

/** The content of the sheet; `JargonTerm` holds the Sheet root and the trigger. */
export function JargonSheet({ id }: { id: TermId }) {
  const { lang } = useMiniapp()
  const closeRef = useRef<HTMLButtonElement>(null)
  const other = otherLanguage(lang)
  const shown = translate(`jargon.${id}.term`, lang)
  const small = translate(`jargon.${id}.term`, other)
  return (
    <SheetContent
      side="bottom"
      showCloseButton={false}
      data-testid="jargon-sheet"
      aria-describedby={undefined}
      className="max-h-[85%] gap-0 overflow-y-auto rounded-t-2xl pb-2"
      onOpenAutoFocus={(event) => {
        event.preventDefault()
        closeRef.current?.focus()
      }}
    >
      <SheetHeader className="gap-0.5 px-4 pt-5 pb-3">
        <SheetTitle lang={shown.fallback ? shown.lang : undefined} className="text-xl font-medium">
          {shown.text}
        </SheetTitle>
        <p data-testid="jargon-sheet-other" lang={small.lang} className="text-caption text-muted-foreground">
          {small.text}
        </p>
      </SheetHeader>
      <div className="flex flex-col gap-3 px-4 pb-4">
        <Body id={id} />
        <p className="text-caption text-muted-foreground">{t('lens.footer', lang)}</p>
      </div>
      <div className="border-t px-4 py-3">
        <SheetClose asChild>
          <Button ref={closeRef} data-testid="jargon-sheet-close" variant="outline" size="lg" className="w-full">
            {t('lens.close', lang)}
          </Button>
        </SheetClose>
      </div>
    </SheetContent>
  )
}

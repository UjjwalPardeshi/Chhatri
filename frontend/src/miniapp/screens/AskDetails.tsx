/**
 * The Details sheet of an answer (screens 5.2): who answered, the model id when a model ran, the time, and on a
 * FALLBACK or SIMULATED answer why a backup was used. The merchant never sees a confidence number. The provider is
 * shown as it is (rules, sarvam, template ...), and the model is the id the server echoed, so nothing is invented here.
 */
import { useRef } from 'react'

import type { AiLabel } from '../api/ask'
import { reasonKey, ta } from '../copy/ask'
import { formatDateTime } from '../lib/format'
import type { Lang } from '../lib/lang'
import { t } from '../lib/copy'
import { Button } from '../ui/button'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet'

function Row({ label, children, testId }: { label: string; children: React.ReactNode; testId: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd data-testid={testId} className="text-sm text-foreground">
        {children}
      </dd>
    </div>
  )
}

export function AskDetails({ label, answeredAt, lang, askId }: { label: AiLabel; answeredAt: string | null; lang: Lang; askId: string }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const reason = label.fallback_reason
  const key = reason === null ? null : reasonKey(reason)
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button data-testid={`ask-details-${askId}`} variant="ghost" className="-mr-3 h-11">
          {ta('ask.details', lang)}
        </Button>
      </SheetTrigger>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        data-testid="ask-details-sheet"
        className="max-h-[85%] gap-0 overflow-y-auto rounded-t-2xl pb-2"
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          closeRef.current?.focus()
        }}
      >
        <SheetHeader className="gap-0.5 px-4 pt-5 pb-3">
          <SheetTitle className="text-xl font-medium">{ta('ask.details', lang)}</SheetTitle>
          <SheetDescription className="text-caption">{askId}</SheetDescription>
        </SheetHeader>
        <dl className="flex flex-col gap-3 px-4 pb-4">
          <Row label={ta('ask.details.provider', lang)} testId="ask-details-provider">
            <span lang="en">{label.provider}</span>
          </Row>
          {label.model === null ? null : (
            <Row label={ta('ask.details.model', lang)} testId="ask-details-model">
              <span lang="en" className="font-code">{label.model}</span>
            </Row>
          )}
          <Row label={ta('ask.details.time', lang)} testId="ask-details-time">
            <span className="num">{formatDateTime(answeredAt, lang)}</span>
          </Row>
          {label.mode === 'LIVE' || reason === null ? null : (
            <Row label={ta('ask.details.reason', lang)} testId="ask-details-reason">
              {key === null ? null : <span className="block">{ta(key, lang)}</span>}
              <span lang="en" className="block font-code text-caption text-ink-3">{reason}</span>
            </Row>
          )}
        </dl>
        <div className="border-t px-4 py-3">
          <SheetClose asChild>
            <Button ref={closeRef} data-testid="ask-details-close" variant="outline" size="lg" className="w-full">
              {t('source.close', lang)}
            </Button>
          </SheetClose>
        </div>
      </SheetContent>
    </Sheet>
  )
}

/**
 * The source badge (H13, fs-04 10.3, design system 11.4): a pill that says which system a number or a check came
 * from, the record's time and its origin word (SIMULATED or LIVE; a fixed setting shows none). It says "Source", never
 * "certified": it names where a value came from, and no outside body verified it. Tapping it opens a bottom sheet with
 * the record, the time, the type of source and the policy clause. A value without a source shows "Source missing" in
 * the blocked tone, and no screen draws a number that way on purpose.
 */
import { BadgeCheck, CircleX } from 'lucide-react'
import { useRef } from 'react'

import type { Source } from '../../api/types'
import { t, type CopyKey } from '../lib/copy'
import { cn } from '../lib/cn'
import { formatClock, formatDateTime } from '../lib/format'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { Button } from '../ui/button'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet'

const ORIGIN_TAG: Readonly<Record<'LIVE' | 'SIMULATED', string>> = { LIVE: 'bg-live-soft text-live-ink', SIMULATED: 'bg-demo-soft text-demo' }

/** The record id after the colon of `alert:A-20250818-01`. */
const idOfRef = (ref: string): string | null => ref.split(':')[1] ?? null

/** The clause chips name the parent clause: C4.1 shows under C4 (copy deck 5.3). */
export function clauseTitle(clause: string, lang: Lang): string | null {
  const parent = clause.split('.')[0]
  const key = `clause.${parent}`
  return Object.hasOwn(CLAUSE_KEYS, key) ? t(CLAUSE_KEYS[key], lang) : null
}
const CLAUSE_KEYS: Readonly<Record<string, CopyKey>> = {
  'clause.C1': 'clause.C1',
  'clause.C2': 'clause.C2',
  'clause.C3': 'clause.C3',
  'clause.C4': 'clause.C4',
  'clause.C5': 'clause.C5',
  'clause.C6': 'clause.C6',
  'clause.C7': 'clause.C7',
  'clause.C8': 'clause.C8',
  'clause.C9': 'clause.C9',
  'clause.C10': 'clause.C10',
  'clause.C11': 'clause.C11',
  'clause.C12': 'clause.C12',
}

/** The words on the pill, from the fixed catalogue of labels (one per source kind). The API's own label stays English. */
export function sourceLabel(source: Source, lang: Lang, rulesVersion: string): string {
  switch (source.kind) {
    case 'RULES':
      return t('src.RULES', lang, { rules_version: rulesVersion })
    case 'CLAUSE':
      return source.clause === null ? source.label : t('src.CLAUSE', lang, { clause: source.clause })
    case 'ALERT': {
      const id = idOfRef(source.ref)
      return id === null ? source.label : t('src.ALERT', lang, { alert_id: id })
    }
    default:
      return t(`src.${source.kind}`, lang)
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  )
}

function SourceSheet({ source, label }: { source: Source; label: string }) {
  const { lang } = useMiniapp()
  const closeRef = useRef<HTMLButtonElement>(null)
  const clause = source.clause === null ? null : clauseTitle(source.clause, lang)
  return (
    <SheetContent
      side="bottom"
      showCloseButton={false}
      data-testid="source-sheet"
      className="max-h-[85%] gap-0 overflow-y-auto rounded-t-2xl pb-2"
      onOpenAutoFocus={(event) => {
        event.preventDefault()
        closeRef.current?.focus()
      }}
    >
      <SheetHeader className="gap-0.5 px-4 pt-5 pb-3">
        <SheetTitle className="text-xl font-medium">{label}</SheetTitle>
        <SheetDescription className="text-caption">{t('source.sheet_desc', lang)}</SheetDescription>
      </SheetHeader>
      <dl className="flex flex-col gap-3 px-4 pb-4">
        <Field label={t('chip.field.record', lang)}>
          <span lang="en" className="block">{source.label}</span>
          <span className="mt-0.5 block break-all font-code text-caption text-ink-2">{source.ref}</span>
        </Field>
        {source.as_of === null ? null : <Field label={t('chip.field.time', lang)}><span className="num">{formatDateTime(source.as_of, lang)}</span></Field>}
        <Field label={t('chip.field.origin', lang)}>
          <span data-testid="source-sheet-origin" className="font-medium">{source.origin}</span>
          <span className="block text-caption text-ink-3">{t(`origin.${source.origin}.hint`, lang)}</span>
        </Field>
        {source.clause === null ? null : (
          <Field label={t('chip.field.clause', lang)}>
            <span className="font-medium">{source.clause}</span>
            {clause === null ? null : <span className="text-ink-2"> · {clause}</span>}
          </Field>
        )}
      </dl>
      <div className="border-t px-4 py-3">
        <SheetClose asChild>
          <Button ref={closeRef} data-testid="source-sheet-close" variant="outline" size="lg" className="w-full">
            {t('source.close', lang)}
          </Button>
        </SheetClose>
      </div>
    </SheetContent>
  )
}

const CHIP =
  'relative inline-flex min-h-6 max-w-full items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1 text-left text-xs font-medium text-ink-2 outline-none after:absolute after:inset-x-0 after:-inset-y-2.5 after:content-[""] focus-visible:ring-[3px] focus-visible:ring-ring/50 print:border-line-strong'

export function SourceBadge({ source, rulesVersion }: { source: Source; rulesVersion: string }) {
  const { lang } = useMiniapp()
  const label = sourceLabel(source, lang, rulesVersion)
  const clause = source.kind === 'RULES' && source.clause !== null ? ` · ${source.clause}` : ''
  const time = source.as_of === null ? '' : ` · ${formatClock(source.as_of)}`
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button type="button" data-testid="source-badge" data-kind={source.kind} data-origin={source.origin} aria-haspopup="dialog" title={t('chip.tap', lang)} className={CHIP}>
          <BadgeCheck className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
          <span>
            {label}
            {clause}
            <span className="num text-ink-3">{time}</span>
          </span>
          {source.origin === 'CONFIG' ? null : (
            <span className={cn('shrink-0 rounded-sm px-1.5 py-0.5 text-2xs tracking-wide', ORIGIN_TAG[source.origin])}>{source.origin}</span>
          )}
        </button>
      </SheetTrigger>
      <SourceSheet source={source} label={label} />
    </Sheet>
  )
}

/** A number or a check that has no source: the badge says so in words, and the tests that read a screen fail on it. */
export function MissingSource() {
  const { lang } = useMiniapp()
  return (
    <span data-testid="source-missing" className="inline-flex min-h-6 items-center gap-1.5 rounded-lg bg-blocked-soft px-2.5 py-1 text-xs font-medium text-blocked">
      <CircleX className="size-3.5 shrink-0" aria-hidden="true" />
      {t('badge.source_missing', lang)}
    </span>
  )
}

/** The badges of one value, or "Source missing" when it has none. */
export function SourceBadges({ sources, rulesVersion, testId }: { sources: readonly Source[]; rulesVersion: string; testId?: string }) {
  return (
    <div data-testid={testId} className="flex flex-wrap gap-x-2 gap-y-5 pt-2">
      {sources.length === 0 ? <MissingSource /> : sources.map((source) => <SourceBadge key={source.ref} source={source} rulesVersion={rulesVersion} />)}
    </div>
  )
}

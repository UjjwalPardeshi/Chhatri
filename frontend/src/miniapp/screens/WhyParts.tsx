/**
 * The blocks of S6 (fs-04 8, screens and flows 4.6): the formula in the engine's own words, "Your numbers" with the
 * sources of every row, and, for a decision with no amount, why a person is looking or why it was not paid. The app
 * recomputes nothing: every figure and sentence is read from the receipt.
 */
import { JargonTerm } from '../components/JargonTerm'
import { FormulaBlock } from '../components/FormulaBlock'
import { SourceBadges } from '../components/SourceBadge'
import { langAttr } from '../components/StepperLine'
import type { CopyKey } from '../lib/copy'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Skeleton } from '../ui/skeleton'
import { ClaimsHeading } from './ClaimsHeading'
import type { WhyRow, WhyValue } from './WhyRows'

const BLOCK = 'flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm'

export function WhyFormula({ en, hi }: { en: string; hi: string }) {
  const { lang } = useMiniapp()
  return (
    <section className={BLOCK}>
      <ClaimsHeading className="text-md font-medium">{t('receipt.row.formula', lang)}</ClaimsHeading>
      <FormulaBlock testId="why-formula" en={en} hi={hi} />
    </section>
  )
}

function Value({ value }: { value: WhyValue }) {
  const { lang } = useMiniapp()
  return <>{value.kind === 'copy' ? t(value.key, lang) : value.text}</>
}

function Label({ row }: { row: WhyRow }) {
  const { lang } = useMiniapp()
  if (row.labelKey === null) return <span lang={langAttr('en', lang)}>{row.labelEn}</span>
  const label = t(row.labelKey, lang)
  return row.term === null ? <>{label}</> : <JargonTerm id={row.term}>{label}</JargonTerm>
}

export function WhyNumbers({ rows, rulesVersion }: { rows: readonly WhyRow[]; rulesVersion: string }) {
  const { lang } = useMiniapp()
  return (
    <section className={BLOCK}>
      <ClaimsHeading className="text-md font-medium">{t('why.numbers', lang)}</ClaimsHeading>
      <dl data-testid="why-numbers" className="flex flex-col divide-y">
        {rows.map((row) => (
          <div key={row.key} data-testid={`why-row-${row.key}`} className="flex flex-wrap items-baseline justify-between gap-x-3 py-2 first:pt-0 last:pb-0">
            <dt className="min-w-0 flex-1 text-sm text-ink-2">
              <Label row={row} />
            </dt>
            <dd data-testid={`why-value-${row.key}`} className="num text-md font-medium text-foreground">
              <Value value={row.value} />
            </dd>
            <dd className="basis-full">
              <SourceBadges sources={row.sources} rulesVersion={rulesVersion} testId="why-badges" />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

type PersonProps = { heading: CopyKey; intro: CopyKey | null; lines: readonly CopyKey[] }

/** A decision with no amount: why a person is looking, or why it was not paid, in plain words. */
export function WhyNoAmount({ heading, intro, lines }: PersonProps) {
  const { lang } = useMiniapp()
  return (
    <section data-testid="why-no-amount" className={BLOCK}>
      <ClaimsHeading className="text-md font-medium">{t(heading, lang)}</ClaimsHeading>
      {intro === null ? null : <p className="text-sm text-foreground">{t(intro, lang)}</p>}
      {lines.length === 0 ? null : (
        <ul data-testid="why-reasons" className="flex list-disc flex-col gap-1.5 ps-5 text-sm text-foreground">
          {lines.map((key) => (
            <li key={key}>{t(key, lang)}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** A formula bar and three rows. */
export function WhySkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-4">
      <Skeleton className="h-24 w-full rounded-xl" />
      <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-6 w-1/2 rounded-lg" />
          </div>
        ))}
      </div>
    </output>
  )
}

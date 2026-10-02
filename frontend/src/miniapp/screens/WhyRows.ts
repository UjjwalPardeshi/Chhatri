/**
 * The rows of "Your numbers" (fs-04 S6, H2): one row per money fact of the receipt, in the order the API sends them,
 * each with the sources the API names for it. The label is a copy key by the fact's key (the API sends English
 * only), the value is the API's own text, and nothing is computed. A fact this app has no label for keeps the API's
 * English label, marked as English by the screen. "half" is the one value that is a word, so it has its own key.
 */
import type { ReceiptFact, Source } from '../../api/types'
import type { TermId } from '../glossary'
import { t, type CopyKey } from '../lib/copy'
import type { Lang } from '../lib/lang'

export type WhyValue = { kind: 'copy'; key: CopyKey } | { kind: 'text'; text: string }

export type WhyRow = {
  key: string
  labelKey: CopyKey | null
  /** The API's English label: shown only where there is no `labelKey`. */
  labelEn: string
  /** The glossary term that explains the label, where the lens has one. */
  term: TermId | null
  value: WhyValue
  sources: Source[]
}

const LABELS: Readonly<Record<string, { key: CopyKey; term: TermId | null }>> = {
  expected_day: { key: 'why.row.expected_day', term: 'expected_day' },
  area_index: { key: 'why.row.area_index', term: null },
  drop_pct: { key: 'why.row.area_drop', term: 'area_drop' },
  days: { key: 'why.row.days', term: null },
  share: { key: 'why.row.share', term: 'payout_share' },
  cap: { key: 'why.row.cap', term: 'daily_cap' },
  amount: { key: 'why.row.amount', term: null },
}

const valueOf = (value: string): WhyValue => (value.toLowerCase() === 'half' ? { kind: 'copy', key: 'why.value.half' } : { kind: 'text', text: value })

export function whyRows(facts: readonly ReceiptFact[]): WhyRow[] {
  return facts.map((fact) => {
    const label = Object.hasOwn(LABELS, fact.key) ? LABELS[fact.key] : null
    return { key: fact.key, labelKey: label?.key ?? null, labelEn: fact.label_en, term: label?.term ?? null, value: valueOf(fact.value), sources: fact.sources }
  })
}

/** The label in the language shown; the API's English label (marked as English) where this app has none. */
export function rowLabel(row: WhyRow, lang: Lang): { text: string; lang: Lang | undefined } {
  return row.labelKey === null ? { text: row.labelEn, lang: lang === 'en' ? undefined : 'en' } : { text: t(row.labelKey, lang), lang: undefined }
}

export const rowValue = (value: WhyValue, lang: Lang): string => (value.kind === 'copy' ? t(value.key, lang) : value.text)

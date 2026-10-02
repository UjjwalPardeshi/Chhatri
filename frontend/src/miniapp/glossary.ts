/**
 * The glossary of the jargon lens (H20, fs-04 section 11): the 15 insurance terms, keyed by id. The words live in the
 * copy dictionaries as `jargon.<id>.term|what|example` (copy deck 7), so Hindi and English stay complete and checked
 * like every other string. A sentence may hold `{placeholders}` (a number of days, a cap): `GET /api/policy` fills them
 * through `rulesParams`, so a change of the rules reaches the lens. Examples use the golden demo numbers and say so;
 * `glossary.test.ts` checks each one against the mock fixtures.
 */
import { translate, type CopyKey, type CopyParams, type Translated } from './lib/copy'
import type { Lang } from './lib/lang'

export const TERM_IDS = [
  'waiting_period',
  'alert',
  'expected_day',
  'area_drop',
  'payout_share',
  'daily_cap',
  'annual_limit',
  'premium',
  'prepaid_through',
  'settlement',
  'edi_holiday',
  'kyc',
  'referred',
  'audit_fingerprint',
  'rules_version',
] as const

export type TermId = (typeof TERM_IDS)[number]
export type TermPart = 'term' | 'what' | 'example'

export function isTermId(value: unknown): value is TermId {
  return typeof value === 'string' && (TERM_IDS as readonly string[]).includes(value)
}

/** The copy key of one part of a term (all 45 exist: the type checks it). */
export const termKey = (id: TermId, part: TermPart): Extract<CopyKey, `jargon.${TermId}.${TermPart}`> => `jargon.${id}.${part}`

export type TermText = { term: Translated; what: Translated; example: Translated }

/** The three parts of a term in `lang`, with the rule numbers filled in. A part that fell back to another language says so. */
export function termText(id: TermId, lang: Lang, params: CopyParams): TermText {
  return {
    term: translate(termKey(id, 'term'), lang, params),
    what: translate(termKey(id, 'what'), lang, params),
    example: translate(termKey(id, 'example'), lang, params),
  }
}

/** The language shown small beside the large one (the sheet names the term in both). */
export const otherLanguage = (lang: Lang): Lang => (lang === 'en' ? 'hi' : 'en')

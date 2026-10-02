/**
 * Numbers and dates for the active language (fs-04 section 13, AC-35): Indian digit grouping and ASCII digits in
 * every language, through the `-u-nu-latn` locale extension (the default Marathi format uses Devanagari digits).
 * Money is never formatted here: the screens show the API's `*_label` as given.
 */
import { hhmm } from '../../lib/time'
import type { Lang } from './lang'

const NONE = '—'
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/

const locale = (lang: Lang): string => `${lang}-IN-u-nu-latn`

const numberFormats = new Map<Lang, Intl.NumberFormat>()
const dateFormats = new Map<Lang, Intl.DateTimeFormat>()

function numberFormat(lang: Lang): Intl.NumberFormat {
  const known = numberFormats.get(lang)
  if (known) return known
  const created = new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 20 })
  numberFormats.set(lang, created)
  return created
}

/** The calendar day is formatted at UTC from the date part as written, so the device's time zone never moves it. */
function dateFormat(lang: Lang): Intl.DateTimeFormat {
  const known = dateFormats.get(lang)
  if (known) return known
  const created = new Intl.DateTimeFormat(locale(lang), { day: 'numeric', month: 'long', timeZone: 'UTC' })
  dateFormats.set(lang, created)
  return created
}

/** 1234567 to "12,34,567", in ASCII digits whatever the language. */
export function formatNumber(value: number, lang: Lang): string {
  return numberFormat(lang).format(value)
}

/** "2025-08-25" (or a timestamp of that day) to "25 August" / "25 अगस्त" / "25 ऑगस्ट". */
export function formatDate(iso: string | null | undefined, lang: Lang): string {
  const match = iso ? ISO_DATE.exec(iso) : null
  if (!match) return NONE
  return dateFormat(lang).format(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))))
}

/** The wall-clock time of an IST timestamp as written ("17:05"). */
export function formatClock(iso: string | null | undefined): string {
  return hhmm(iso)
}

/** "19 August, 17:05": the date in the active language and the time, for the replay clock. */
export function formatDateTime(iso: string | null | undefined, lang: Lang): string {
  const date = formatDate(iso, lang)
  const clock = formatClock(iso)
  return date === NONE || clock === NONE ? NONE : `${date}, ${clock}`
}

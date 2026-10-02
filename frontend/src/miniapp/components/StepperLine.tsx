/**
 * A line of words on the claim screens: fixed copy (with its facts) or the API's own sentence in two languages. The
 * sentence is shown in the language of the app, Hindi for Marathi (the API has no Marathi) and English where a pair
 * has no Hindi; an element whose language differs from the app's carries its own `lang` (fs-04 section 13).
 */
import type { Line } from '../hooks/trackerModel'
import { translate } from '../lib/copy'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'

export type Shown = { text: string; lang: Lang }

/** The catalogue has no Hindi for the case chip, so it reads in English in every language (fs-04 section 8, S5). */
const ENGLISH_ONLY: ReadonlySet<string> = new Set(['CASE_CHIP'])

const present = (text: string | null): text is string => text !== null && text !== ''

export function pickBilingual(lang: Lang, hi: string | null, en: string | null): Shown | null {
  if (lang === 'en' && present(en)) return { text: en, lang: 'en' }
  if (present(hi)) return { text: hi, lang: 'hi' }
  return present(en) ? { text: en, lang: 'en' } : null
}

export function lineShown(line: Line, lang: Lang): Shown | null {
  if (line.kind === 'api') return pickBilingual(lang, line.hi, line.en)
  const found = translate(line.key, lang, line.params)
  return { text: found.text, lang: ENGLISH_ONLY.has(line.key) ? 'en' : found.lang }
}

/** The `lang` attribute of an element: only when it differs from the app's, which the root already carries. */
export const langAttr = (shown: Lang, app: Lang): Lang | undefined => (shown === app ? undefined : shown)

export function LineText({ line, className, testId }: { line: Line; className?: string; testId?: string }) {
  const { lang } = useMiniapp()
  const shown = lineShown(line, lang)
  if (shown === null) return null
  return (
    <p data-testid={testId} lang={langAttr(shown.lang, lang)} className={className}>
      {shown.text}
    </p>
  )
}

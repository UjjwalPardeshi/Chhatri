/**
 * The language of the app for a screen (fs-04 section 13). The choice itself (URL, then the stored preference, then the
 * merchant's language, then Hindi) is made by the shell's provider; this hook gives a screen what it needs from it: the
 * language, the way to change it, the options the flags allow (Marathi only while `n8_marathi` is on), a translator
 * bound to the language, and whether some text falls back to Hindi (the note of S9).
 */
import { useCallback, useMemo } from 'react'

import { isFeatureEnabled } from '../../features'
import { marathiCoverage, t, translate, type CopyKey, type CopyParams, type Translated } from '../lib/copy'
import { LANGS, type Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'

export type LanguageApi = {
  lang: Lang
  setLang: (lang: Lang) => void
  languages: readonly Lang[]
  t: (key: CopyKey, params?: CopyParams) => string
  /** The same, with the language the text came from, for the element's own `lang` when it fell back. */
  translate: (key: CopyKey, params?: CopyParams) => Translated
  /** True while Marathi is chosen and some text is not translated yet. */
  fallbackNote: boolean
}

export function useLanguage(): LanguageApi {
  const { lang, setLang } = useMiniapp()
  const marathi = isFeatureEnabled('n8_marathi')
  const languages = useMemo(() => LANGS.filter((candidate) => candidate !== 'mr' || marathi), [marathi])
  const bound = useCallback((key: CopyKey, params?: CopyParams) => t(key, lang, params), [lang])
  const detailed = useCallback((key: CopyKey, params?: CopyParams) => translate(key, lang, params), [lang])
  const { translated, total } = marathiCoverage()
  return { lang, setLang, languages, t: bound, translate: detailed, fallbackNote: lang === 'mr' && translated < total }
}

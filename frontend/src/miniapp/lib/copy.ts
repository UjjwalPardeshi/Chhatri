/**
 * `t(key, lang)`: the mini-app's strings with the fallback chain mr to hi to en (fs-04 section 13). Hindi and
 * English are complete, so the chain always ends. A string that came from another language says so in
 * `Translated.lang`, and the screen puts that value in the element's `lang` attribute (AC-33).
 */
import { en, type CopyKey } from '../copy/en'
import { hi } from '../copy/hi'
import { mr } from '../copy/mr'
import type { Lang } from './lang'

export type { CopyKey }
export type CopyParams = Readonly<Record<string, string | number>>
export type Translated = { text: string; lang: Lang; fallback: boolean }
type Dictionary = Readonly<Partial<Record<CopyKey, string>>>
export type Dictionaries = Readonly<Record<Lang, Dictionary>>

const CHAIN: Readonly<Record<Lang, readonly Lang[]>> = { mr: ['mr', 'hi', 'en'], hi: ['hi', 'en'], en: ['en'] }
const PLACEHOLDER = /\{(\w+)\}/g

/** Replaces each {name} with its value. A name with no value stays visible, so a gap is seen, never guessed. */
function fill(template: string, params: CopyParams): string {
  return template.replace(PLACEHOLDER, (whole, name: string) => (name in params ? String(params[name]) : whole))
}

export function createTranslator(dictionaries: Dictionaries) {
  function translate(key: CopyKey, lang: Lang, params: CopyParams = {}): Translated {
    for (const candidate of CHAIN[lang]) {
      const template = dictionaries[candidate][key]
      if (template !== undefined) return { text: fill(template, params), lang: candidate, fallback: candidate !== lang }
    }
    throw new Error(`missing copy key ${key}`)
  }
  return { translate }
}

const shipped = createTranslator({ mr, hi, en })

export const translate = shipped.translate

export function t(key: CopyKey, lang: Lang, params: CopyParams = {}): string {
  return shipped.translate(key, lang, params).text
}

/** How much of the English key list Marathi has (S9 says "Some text is shown in Hindi." while this is short). */
export function marathiCoverage(): { translated: number; total: number } {
  const keys = Object.keys(en) as CopyKey[]
  return { translated: keys.filter((key) => mr[key] !== undefined).length, total: keys.length }
}

/** The three languages of the mini-app (fs-04 section 13). `mr` is Wave 4 and sits behind `n8_marathi`. */

export const LANGS = ['hi', 'en', 'mr'] as const
export type Lang = (typeof LANGS)[number]

export const DEFAULT_LANG: Lang = 'hi'

export function isLang(value: unknown): value is Lang {
  return typeof value === 'string' && (LANGS as readonly string[]).includes(value)
}

/** Marathi draft (card 6.7): every key, the same placeholders, Devanagari only, no nukta (copy deck 1.2 and 19). */
import { describe, expect, it } from 'vitest'

import { en, type CopyKey } from './en'
import { mr } from './mr'

const keys = Object.keys(en) as CopyKey[]
const placeholders = (text: string) =>
  [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1].replace(/_(hi|en|mr)$/, '')).toSorted()
const WHITELIST = /\b(KYC|Paytm|Sarvam|Gemini|WhatsApp|Soundbox|EDI|UPI|SMS|AI|OTP|PIN|IRDAI|IMD|SIMULATED|LIVE|FALLBACK|for|Business|English|ID|OK|PDF|JPG|PNG|WebP|MB)\b/g

describe('mr', () => {
  it('has text for every key', () => {
    expect(keys.filter((key) => !mr[key] || mr[key]!.trim() === '')).toEqual([])
  })

  it('uses the same placeholders as English', () => {
    for (const key of keys) expect([key, placeholders(mr[key]!)]).toEqual([key, placeholders(en[key])])
  })

  it('has no nukta and no stray Latin words', () => {
    for (const key of keys) {
      const text = mr[key]!.replace(/\{\w+\}/g, '').replace(WHITELIST, '')
      expect([key, /़/.test(text)]).toEqual([key, false])
      const strayLatin = /[ऀ-ॿ]/.test(text) && /[A-Za-z]{2,}/.test(text)
      expect([key, strayLatin]).toEqual([key, false])
    }
  })
})

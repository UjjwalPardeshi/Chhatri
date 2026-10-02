/** The glossary of the jargon lens: every term complete in Hindi and English, every screen's term ids real, examples in line with the mock fixtures. */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { formatInr } from '../lib/money'
import { POLICY_RULES, RAMESH, zonePremiumPaise } from '../mock/fixtures'
import { isTermId, TERM_IDS, termKey, termText } from './glossary'

describe('the glossary', () => {
  it('has a term, a plain explanation and an example in Hindi and English for each of the 15 ids', () => {
    expect(TERM_IDS).toHaveLength(15)
    for (const id of TERM_IDS) {
      for (const lang of ['hi', 'en'] as const) {
        const { term, what, example } = termText(id, lang, {})
        expect([id, lang, term.text.length > 0, what.text.length > 0, example.text.length > 0]).toEqual([id, lang, true, true, true])
        expect(term.lang).toBe(lang)
      }
    }
  })

  it('knows its ids and builds keys from them', () => {
    expect(isTermId('premium')).toBe(true)
    expect(isTermId('offer')).toBe(false)
    expect(termKey('kyc', 'what')).toBe('jargon.kyc.what')
  })

  it('names only real term ids in the screens (a static scan of JargonTerm id="...")', () => {
    const dir = join(__dirname, 'screens')
    const used = readdirSync(dir)
      .filter((file) => file.endsWith('.tsx') && !file.endsWith('.test.tsx'))
      .flatMap((file) => [...readFileSync(join(dir, file), 'utf8').matchAll(/(?:JargonTerm id|ids)=\{?['"[]+([a-z_'", ]+)/g)].flatMap((m) => m[1].match(/[a-z_]+/g) ?? []))
    for (const id of used) expect(isTermId(id)).toBe(true)
  })

  it('shows the demo prices of the fixtures in the premium examples', () => {
    const perDay = formatInr(zonePremiumPaise(RAMESH.zone_id))
    const total = formatInr(zonePremiumPaise(RAMESH.zone_id) * POLICY_RULES.premium.first_payment_days)
    for (const id of ['premium', 'prepaid_through'] as const) {
      const example = termText(id, 'en', {}).example.text
      expect(example).toContain(id === 'premium' ? perDay : total)
    }
  })
})

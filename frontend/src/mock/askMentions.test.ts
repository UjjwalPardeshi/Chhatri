import { describe, expect, it } from 'vitest'

import { findMentions } from './askMentions'

describe('findMentions', () => {
  it('reads "डेढ़ हज़ार रुपये" as ₹1,500', () => {
    const [m, ...rest] = findMentions('डेढ़ हज़ार रुपये कब मिलेंगे', 2025)
    expect(rest).toEqual([])
    expect(m).toMatchObject({ id: 'm1', kind: 'amount', heard: 'डेढ़ हज़ार', value: '₹1,500', value_paise: 150000, chip_hi: '₹1,500 — सही है?', chip_en: '₹1,500 — is that right?' })
  })

  it('reads digits, English words and the Indian scales', () => {
    expect(findMentions('I got 4380 rupees', 2025)[0]).toMatchObject({ value: '₹4,380', value_paise: 438000 })
    expect(findMentions('two thousand five hundred', 2025)[0]).toMatchObject({ value: '₹2,500' })
    expect(findMentions('ढाई सौ', 2025)[0]).toMatchObject({ value: '₹250' })
    expect(findMentions('सवा लाख', 2025)[0]).toMatchObject({ value: '₹1,25,000' })
    expect(findMentions('पाँच सौ रुपये', 2025)[0]).toMatchObject({ value: '₹500' })
  })

  it('reads a date and does not take its day for money', () => {
    const found = findMentions('19 August को पैसे आए', 2025)
    expect(found).toHaveLength(1)
    expect(found[0]).toMatchObject({ kind: 'date', value: '19 August', value_date: '2025-08-19', chip_en: '19 August — is that right?' })
  })

  it('numbers the mentions in the order they were said', () => {
    const found = findMentions('1500 rupees on 19 August', 2025)
    expect(found.map((m) => [m.id, m.kind])).toEqual([['m1', 'amount'], ['m2', 'date']])
  })

  it('gives a word it cannot read no value, so the merchant types it', () => {
    const [m] = findMentions('डेढ़ रुपये', 2025)
    expect(m).toMatchObject({ kind: 'amount', heard: 'डेढ़', value: null, value_paise: null })
    expect(m.chip_en).toContain('Please type the number')
  })

  it('does not guess what कल means', () => {
    const [m] = findMentions('कल पैसे मिले', 2025)
    expect(m).toMatchObject({ kind: 'date', heard: 'कल', value: null, value_date: null })
  })

  it('finds nothing in a question with no amount or date', () => {
    expect(findMentions('मेरा कवर कब शुरू होता है', 2025)).toEqual([])
    expect(findMentions('one question', 2025)).toEqual([])
  })
})

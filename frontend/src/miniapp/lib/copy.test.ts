/** The copy chain mr to hi to en and the completeness rule (fs-04 section 13, AC-33). */
import { describe, expect, it } from 'vitest'

import { en } from '../copy/en'
import { hi } from '../copy/hi'
import { mr } from '../copy/mr'
import { createTranslator, marathiCoverage, t, translate } from './copy'

const placeholders = (text: string): string[] => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).toSorted()

describe('the copy dictionaries', () => {
  it('hindi and english have the same keys', () => {
    expect(Object.keys(hi).toSorted()).toEqual(Object.keys(en).toSorted())
  })

  it('hindi and english use the same placeholders in every string', () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect([key, placeholders(hi[key])]).toEqual([key, placeholders(en[key])])
    }
  })

  it('has no empty string in either language', () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect([key, en[key].trim() === '']).toEqual([key, false])
      expect([key, hi[key].trim() === '']).toEqual([key, false])
    }
  })

  it('marathi covers every key of the English list (card 6.7), and the measured count says so', () => {
    expect(Object.keys(mr).toSorted()).toEqual(Object.keys(en).toSorted())
    expect(marathiCoverage()).toEqual({ translated: Object.keys(en).length, total: Object.keys(en).length })
  })
})

describe('translate', () => {
  it('falls back mr to hi to en and marks the fallback with lang', () => {
    const translator = createTranslator({
      mr: { 'nav.home': 'मुख्यपृष्ठ' },
      hi: { 'nav.home': 'होम', 'nav.claims': 'दावे' },
      en: { 'nav.home': 'Home', 'nav.claims': 'Claims', 'nav.help': 'Help' },
    })
    expect(translator.translate('nav.home', 'mr')).toEqual({ text: 'मुख्यपृष्ठ', lang: 'mr', fallback: false })
    expect(translator.translate('nav.claims', 'mr')).toEqual({ text: 'दावे', lang: 'hi', fallback: true })
    expect(translator.translate('nav.help', 'mr')).toEqual({ text: 'Help', lang: 'en', fallback: true })
    expect(translator.translate('nav.help', 'hi')).toEqual({ text: 'Help', lang: 'en', fallback: true })
    expect(translator.translate('nav.help', 'en')).toEqual({ text: 'Help', lang: 'en', fallback: false })
  })

  it('shows Marathi for mr, and Hindi for a key Marathi does not have yet', () => {
    expect(translate('nav.claims', 'mr')).toEqual({ text: mr['nav.claims'], lang: 'mr', fallback: false })
    expect(translate('nav.claims', 'hi')).toEqual({ text: hi['nav.claims'], lang: 'hi', fallback: false })
    expect(t('nav.claims', 'en')).toBe('Claims')
  })

  it('fills {placeholders} and leaves an unknown one visible', () => {
    expect(t('app.clock', 'en', { time: '19 August, 17:05' })).toBe('Demo date and time: 19 August, 17:05')
    expect(t('error.code', 'en', { code: 'not_found' })).toBe('Error code: not_found')
    expect(t('offline.banner', 'en')).toBe('Offline. Showing data from {time}.')
  })

  it('throws for a key that no language has', () => {
    const translator = createTranslator({ mr: {}, hi: {}, en: {} })
    expect(() => translator.translate('nav.home', 'hi')).toThrow(/missing copy key/)
  })
})

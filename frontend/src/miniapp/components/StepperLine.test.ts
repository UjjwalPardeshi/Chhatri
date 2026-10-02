/** The line of words on the claim screens: the language it shows, the fallbacks, and the case chip that stays English. */
import { describe, expect, it } from 'vitest'

import { en } from '../copy/en'
import { hi } from '../copy/hi'
import { langAttr, lineShown, pickBilingual } from './StepperLine'

describe('pickBilingual', () => {
  it('shows the language of the app, from the pair the API sent', () => {
    expect(pickBilingual('en', 'हिंदी', 'English')).toEqual({ text: 'English', lang: 'en' })
    expect(pickBilingual('hi', 'हिंदी', 'English')).toEqual({ text: 'हिंदी', lang: 'hi' })
  })

  it('shows Hindi for Marathi, because the API has no Marathi', () => {
    expect(pickBilingual('mr', 'हिंदी', 'English')).toEqual({ text: 'हिंदी', lang: 'hi' })
  })

  it('falls back to the other language of the pair, marked with its own language, and to nothing when there is none', () => {
    expect(pickBilingual('hi', null, 'English only')).toEqual({ text: 'English only', lang: 'en' })
    expect(pickBilingual('en', 'सिर्फ़ हिंदी', null)).toEqual({ text: 'सिर्फ़ हिंदी', lang: 'hi' })
    expect(pickBilingual('en', '', '')).toBeNull()
    expect(pickBilingual('hi', null, null)).toBeNull()
  })
})

describe('lineShown', () => {
  it('fills a fixed line with its facts in the language of the app', () => {
    expect(lineShown({ kind: 'copy', key: 'TRACK_DECIDED_AUTO', params: { amount: '₹1,380' } }, 'en')?.text).toBe('Approved ₹1,380')
    expect(lineShown({ kind: 'copy', key: 'TRACK_DECIDED_AUTO', params: { amount: '₹1,380' } }, 'hi')?.text).toBe(hi.TRACK_DECIDED_AUTO.replace('{amount}', '₹1,380'))
  })

  it('keeps the case chip in English in every language, marked as English', () => {
    const chip = { kind: 'copy', key: 'CASE_CHIP', params: { case_id: 'C-2291' } } as const
    expect(lineShown(chip, 'hi')).toEqual({ text: 'Sent to a claims officer · case C-2291', lang: 'en' })
    expect(lineShown(chip, 'en')).toEqual({ text: 'Sent to a claims officer · case C-2291', lang: 'en' })
    expect(en.CASE_CHIP).toBe(hi.CASE_CHIP)
  })

  it('shows the API sentence of a line that came from the API', () => {
    expect(lineShown({ kind: 'api', hi: 'हिंदी', en: 'English' }, 'en')?.text).toBe('English')
  })
})

describe('langAttr', () => {
  it('sets a language only where it differs from the app root', () => {
    expect(langAttr('hi', 'hi')).toBeUndefined()
    expect(langAttr('en', 'hi')).toBe('en')
  })
})

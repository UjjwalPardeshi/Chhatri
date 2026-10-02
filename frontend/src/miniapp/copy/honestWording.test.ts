/**
 * X7 and H4 for the mini-app (PRD X7, copy deck 1.6, fs-09 section 12): no string of the app promises money or
 * approval. The scan uses the promise stems of the backend guard (`conversation/guard.py` PROMISE) and its token rule
 * (a stem matches at the start of a word, after the backend's `normalise`), over every key of the app's dictionaries in
 * every language: en, hi and mr, and the Ask and rights rows. A line that legitimately names an outcome that already
 * exists is listed with the reason, and a listed line that no longer needs it fails the scan.
 */
import { describe, expect, it } from 'vitest'

import { ASK_COPY_KEYS, ta } from './ask'
import { en, type CopyKey } from './en'
import { hi } from './hi'
import { mr } from './mr'
import { RIGHTS_COPY_KEYS, tr } from './rights'

/** `PROMISE.stems` of backend/chhatri/conversation/guard.py, character for character. */
const PROMISE_STEMS = [
  'approv', 'guarantee', 'promis', 'assur', 'sanction', 'refund', 'will be paid', 'will pay',
  'will get', 'youll get', 'will receive', 'will be credited', 'will credit', 'definitely get',
  'surely get', 'मंजूर', 'गारंटी', 'पक्का', 'वादा', 'मिल जाएंग', 'मिल जायेंग', 'मिलेंगे',
  'पैसे मिल', 'रुपये मिल', 'भुगतान मिल', 'भुगतान कर देंगे', 'भुगतान हो जाएग', 'जमा हो जाएग',
  'जमा कर देंगे', 'manjoor', 'manzoor', 'manjur', 'pakka', 'pass ho jayega', 'mil jayenge',
  'mil jayega', 'paisa milega', 'paise milenge', 'payment ho jayega',
]

/** `normalise` of backend/chhatri/conversation/intents.py: no nukta, chandrabindu as anusvara, lower case, words spaced. */
function normalise(text: string): string {
  const folded = text.normalize('NFD').replaceAll('़', '').normalize('NFC').replaceAll('ँ', 'ं').toLowerCase()
  const words = folded.replace(/['’`]/g, '').replace(/[।॥]/g, ' ').replace(/[^\p{L}\p{N}_ऀ-ॣ०-ॿ]+/gu, ' ')
  const joined = words.split(/\s+/).filter((w) => w !== '').join(' ')
  return joined ? ` ${joined} ` : ' '
}

const PROMISE = new RegExp(`(?<!\\S)(?:${[...PROMISE_STEMS].toSorted((a, b) => b.length - a.length).map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'u')
const promises = (text: string): boolean => PROMISE.test(normalise(text.replace(/\{[^{}]*\}/g, ' ')))

/**
 * Lines that name an outcome which already exists (a decision or a payout on record), so a promise stem is what they
 * report: key -> why it may say so.
 */
const NAMES_A_RECORDED_OUTCOME: Readonly<Record<string, string>> = {
  'claim.status.approved_pending': 'the status of a claim whose APPROVED decision exists and whose credit is on its way (fs-04 14.2)',
  TRACK_DECIDED_AUTO: 'the Decided step of a claim the engine has APPROVED, shown once the decision exists (fs-04 9.5)',
  TRACK_DECIDED_OFFICER: "the Decided step after the officer's APPROVED decision (fs-04 9.5, AC-20)",
  REASON_OFFICER_PERSONAL: "the officer's DECLINED reason; the Hindi and Marathi say it could not be approved (backend allows it the same way)",
}

type Line = { key: string; lang: string; text: string }

function lines(): Line[] {
  const keys = Object.keys(en) as CopyKey[]
  const app = keys.flatMap((key) => [
    { key, lang: 'en', text: en[key] },
    { key, lang: 'hi', text: hi[key] },
    { key, lang: 'mr', text: mr[key] ?? '' },
  ])
  const ask = ASK_COPY_KEYS.flatMap((key) => (['en', 'hi'] as const).map((lang) => ({ key, lang, text: ta(key, lang) })))
  const rights = RIGHTS_COPY_KEYS.flatMap((key) => (['en', 'hi'] as const).map((lang) => ({ key, lang, text: tr(key, lang) })))
  return [...app, ...ask, ...rights].filter((line) => line.text !== '')
}

describe('honest wording of the mini-app (X7, H4)', () => {
  it('promises no money and no approval outside the lines that name a recorded outcome', () => {
    const promising = lines().filter((line) => !(line.key in NAMES_A_RECORDED_OUTCOME) && promises(line.text))
    expect(promising.map((line) => `${line.key} [${line.lang}]: ${line.text}`)).toEqual([])
  })

  it('keeps no stale entry in the allow list', () => {
    const promisingKeys = new Set(lines().filter((line) => promises(line.text)).map((line) => line.key))
    expect(Object.keys(NAMES_A_RECORDED_OUTCOME).filter((key) => !promisingKeys.has(key))).toEqual([])
  })

  it('catches what it is for, in English, Hindi and Hinglish', () => {
    expect(promises('You will be paid for tomorrow')).toBe(true)
    expect(promises('आपको पैसे मिल जाएंगे')).toBe(true)
    expect(promises('Your claim is approved')).toBe(true)
    expect(promises('paisa milega kal')).toBe(true)
    expect(promises('Chhatri explains. The rules decide every payout, not this assistant.')).toBe(false)
    expect(promises('{amount} credited')).toBe(false)
  })
})

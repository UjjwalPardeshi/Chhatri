import { describe, expect, it } from 'vitest'

import type { Mention } from '../api/ask'
import { allConfirmed, confirmedIds, isKal, mentionKey, needsTyping, pendingMentions } from './voiceMentions'

const amount: Mention = { id: 'm1', kind: 'amount', heard: 'डेढ़ हज़ार', value: '₹1,500', value_paise: 150000, value_date: null, chip_hi: '', chip_en: '' }
const date: Mention = { id: 'm2', kind: 'date', heard: '19 August', value: '19 August', value_paise: null, value_date: '2025-08-19', chip_hi: '', chip_en: '' }
const kal: Mention = { id: 'm3', kind: 'date', heard: 'कल', value: null, value_paise: null, value_date: null, chip_hi: '', chip_en: '' }
const unread: Mention = { id: 'm4', kind: 'amount', heard: 'डेढ़', value: null, value_paise: null, value_date: null, chip_hi: '', chip_en: '' }

describe('confirmation chips', () => {
  it('has nothing to confirm for a text with no amount or date', () => {
    expect(allConfirmed([], new Set())).toBe(true)
  })

  it('keeps Send off until every chip is confirmed', () => {
    const confirmed = new Set([mentionKey(amount)])
    expect(allConfirmed([amount, date], confirmed)).toBe(false)
    expect(pendingMentions([amount, date], confirmed).map((m) => m.id)).toEqual(['m2'])
    expect(allConfirmed([amount, date], new Set([mentionKey(amount), mentionKey(date)]))).toBe(true)
  })

  it('keeps a confirmation when the words around the amount change, and starts a new amount unconfirmed', () => {
    const confirmed = new Set([mentionKey(amount)])
    const edited: Mention = { ...amount, id: 'm1' }
    const added: Mention = { ...amount, id: 'm2', heard: '2000', value: '₹2,000', value_paise: 200000 }
    expect(allConfirmed([edited], confirmed)).toBe(true)
    expect(pendingMentions([edited, added], confirmed).map((m) => m.id)).toEqual(['m2'])
  })

  it('never confirms words with no value, and asks which day कल means', () => {
    expect(needsTyping(unread)).toBe(true)
    expect(isKal(kal)).toBe(true)
    expect(needsTyping(kal)).toBe(false)
    expect(allConfirmed([unread], new Set([mentionKey(unread)]))).toBe(false)
    expect(allConfirmed([kal], new Set())).toBe(false)
    expect(allConfirmed([kal], new Set([mentionKey(kal, 'yesterday')]))).toBe(true)
  })

  it('lists the confirmed ids for the server', () => {
    expect(confirmedIds([amount, date], new Set([mentionKey(date)]))).toEqual(['m2'])
  })
})

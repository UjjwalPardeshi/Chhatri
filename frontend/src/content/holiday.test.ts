/** The X4 merchant lines are the copy deck 3.3 wording (the backend HOLIDAY_* keys): the lender decides, Chhatri only asks. */
import { describe, expect, it } from 'vitest'

import { LENDER_REASON_CODES } from '../api/types'
import { HOLIDAY, HOLIDAY_REASONS } from './holiday'

const ENDS_EN = 'It moves to the end of your loan with no penalty.'
const ENDS_HI = 'वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।'

describe('HOLIDAY_GRANTED, HOLIDAY_GRANTED_TODAY and HOLIDAY_GRANTED_ON', () => {
  it('says the lender paused tomorrow’s instalment, in both languages', () => {
    expect(HOLIDAY.granted('₹600', 'tomorrow')).toEqual({
      hi: `आपके लेंडर ने कल की ₹600 की किस्त रोक दी है। ${ENDS_HI}`,
      en: `Your lender has paused tomorrow's ₹600 instalment. ${ENDS_EN}`,
    })
  })

  it('says today’s when the instalment is due today', () => {
    expect(HOLIDAY.granted('₹600', 'today')).toEqual({
      hi: `आपके लेंडर ने आज की ₹600 की किस्त रोक दी है। ${ENDS_HI}`,
      en: `Your lender has paused today's ₹600 instalment. ${ENDS_EN}`,
    })
  })

  it('names the date when the instalment is due on another day', () => {
    expect(HOLIDAY.granted('₹600', { on: '2025-08-27' })).toEqual({
      hi: `आपके लेंडर ने 27 अगस्त की ₹600 की किस्त रोक दी है। ${ENDS_HI}`,
      en: `Your lender has paused the ₹600 instalment due on 27 August. ${ENDS_EN}`,
    })
  })
})

describe('HOLIDAY_REFUSED', () => {
  it('gives the lender’s reason and says the payout is not affected', () => {
    expect(HOLIDAY.refused('₹600', 'tomorrow', 'IN_ARREARS')).toEqual({
      hi: 'आपका लेंडर कल की ₹600 की किस्त नहीं रोक सका: लोन की कुछ रकम बकाया है। वह हमेशा की तरह देय है। आपके भुगतान पर इसका कोई असर नहीं पड़ता।',
      en: 'Your lender could not pause the ₹600 instalment due tomorrow: the loan has an amount overdue. It is due as usual. Your payout is not affected.',
    })
  })

  it('reads right for today and for a date', () => {
    expect(HOLIDAY.refused('₹600', 'today', 'NOT_ACTIVE').en).toBe(
      'Your lender could not pause the ₹600 instalment due today: the loan is not active. It is due as usual. Your payout is not affected.',
    )
    const dated = HOLIDAY.refused('₹600', { on: '2025-08-27' }, 'NO_ALLOWANCE')
    expect(dated.en).toBe('Your lender could not pause the ₹600 instalment due on 27 August: your holiday allowance is used up. It is due as usual. Your payout is not affected.')
    expect(dated.hi).toContain('27 अगस्त की ₹600 की किस्त नहीं रोक सका: आपकी किस्त की छुट्टियों की सीमा पूरी हो चुकी है।')
  })

  it('has a fragment for every reason code the lender can give', () => {
    expect(Object.keys(HOLIDAY_REASONS).toSorted()).toEqual([...LENDER_REASON_CODES].toSorted())
    expect(HOLIDAY_REASONS.FLAG_OFF.en).toBe('this loan is not part of the holiday scheme')
  })
})

describe('HOLIDAY_NO_RESPONSE', () => {
  it('says Chhatri could not reach the lender, the instalment is due as usual and the payout is not affected', () => {
    expect(HOLIDAY.noResponse('₹600', 'tomorrow')).toEqual({
      hi: 'हम कल की ₹600 की किस्त के बारे में आपके लेंडर तक नहीं पहुँच सके, इसलिए वह हमेशा की तरह देय है। आपके भुगतान पर इसका कोई असर नहीं पड़ता।',
      en: 'We could not reach your lender about the ₹600 instalment due tomorrow, so it is due as usual. Your payout is not affected.',
    })
    expect(HOLIDAY.noResponse('₹600', { on: '2025-08-27' }).en).toContain('due on 27 August, so it is due as usual.')
  })

  it('never says Chhatri paused anything or promises a grant', () => {
    const lines = [HOLIDAY.refused('₹600', 'tomorrow', 'FLAG_OFF'), HOLIDAY.noResponse('₹600', 'today')]
    for (const line of lines) expect(line.en).not.toMatch(/Chhatri (has )?paused|we paused|will be paused/i)
  })
})

/**
 * The X4 merchant lines (copy deck 3.3, fs-03 section 8): the lender decides the EDI holiday, so a line says
 * "Your lender ..." or that Chhatri could not reach the lender, and never that Chhatri paused anything. The words
 * are the backend keys HOLIDAY_GRANTED, HOLIDAY_GRANTED_TODAY, HOLIDAY_GRANTED_ON, HOLIDAY_REFUSED,
 * HOLIDAY_NO_RESPONSE and HOLIDAY_REASON_* (conversation/messages.py). Shared by the mock backend and the console.
 */
import type { LenderReasonCode } from '../api/types'
import { dateEn, dateHi, type Bilingual } from './catalogue'

/** When the instalment is due, from the day the line is sent: tomorrow, today or another ISO date. */
export type HolidayDay = 'tomorrow' | 'today' | { on: string }

const ENDS_HI = 'वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।'
const ENDS_EN = 'It moves to the end of your loan with no penalty.'
const UNAFFECTED_HI = 'आपके भुगतान पर इसका कोई असर नहीं पड़ता।'
const UNAFFECTED_EN = 'Your payout is not affected.'

/** The reason fragments that follow the colon in HOLIDAY_REFUSED, by the lender's reason code. */
export const HOLIDAY_REASONS: Readonly<Record<LenderReasonCode, Bilingual>> = Object.freeze({
  FLAG_OFF: { hi: 'यह लोन किस्त की छुट्टी की योजना में शामिल नहीं है', en: 'this loan is not part of the holiday scheme' },
  NOT_ACTIVE: { hi: 'लोन चालू नहीं है', en: 'the loan is not active' },
  IN_ARREARS: { hi: 'लोन की कुछ रकम बकाया है', en: 'the loan has an amount overdue' },
  NO_ALLOWANCE: { hi: 'आपकी किस्त की छुट्टियों की सीमा पूरी हो चुकी है', en: 'your holiday allowance is used up' },
})

/** "due {when}": कल / tomorrow, आज / today, or the date (HOLIDAY_REFUSED, HOLIDAY_NO_RESPONSE). */
function dueWhen(day: HolidayDay): { hi: string; en: string } {
  if (day === 'tomorrow') return { hi: 'कल', en: 'tomorrow' }
  if (day === 'today') return { hi: 'आज', en: 'today' }
  return { hi: dateHi(day.on), en: `on ${dateEn(day.on)}` }
}

function granted(instalment: string, day: HolidayDay): Bilingual {
  if (day === 'tomorrow') {
    return { hi: `आपके लेंडर ने कल की ${instalment} की किस्त रोक दी है। ${ENDS_HI}`, en: `Your lender has paused tomorrow's ${instalment} instalment. ${ENDS_EN}` }
  }
  if (day === 'today') {
    return { hi: `आपके लेंडर ने आज की ${instalment} की किस्त रोक दी है। ${ENDS_HI}`, en: `Your lender has paused today's ${instalment} instalment. ${ENDS_EN}` }
  }
  return { hi: `आपके लेंडर ने ${dateHi(day.on)} की ${instalment} की किस्त रोक दी है। ${ENDS_HI}`, en: `Your lender has paused the ${instalment} instalment due on ${dateEn(day.on)}. ${ENDS_EN}` }
}

function refused(instalment: string, day: HolidayDay, reason: LenderReasonCode): Bilingual {
  const when = dueWhen(day)
  const why = HOLIDAY_REASONS[reason]
  return {
    hi: `आपका लेंडर ${when.hi} की ${instalment} की किस्त नहीं रोक सका: ${why.hi}। वह हमेशा की तरह देय है। ${UNAFFECTED_HI}`,
    en: `Your lender could not pause the ${instalment} instalment due ${when.en}: ${why.en}. It is due as usual. ${UNAFFECTED_EN}`,
  }
}

function noResponse(instalment: string, day: HolidayDay): Bilingual {
  const when = dueWhen(day)
  return {
    hi: `हम ${when.hi} की ${instalment} की किस्त के बारे में आपके लेंडर तक नहीं पहुँच सके, इसलिए वह हमेशा की तरह देय है। ${UNAFFECTED_HI}`,
    en: `We could not reach your lender about the ${instalment} instalment due ${when.en}, so it is due as usual. ${UNAFFECTED_EN}`,
  }
}

export const HOLIDAY = { granted, refused, noResponse } as const

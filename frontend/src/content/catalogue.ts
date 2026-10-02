/**
 * Merchant message catalogue: the exact SPEC §13.4 strings (deck wording), filled from decision
 * facts. Shared by the mock backend and the Overview story phones. Amounts are always `formatInr` labels.
 */

export type Bilingual = { hi: string | null; en: string }

export const WEEKDAYS_HI = ['सोमवार', 'मंगलवार', 'बुधवार', 'गुरुवार', 'शुक्रवार', 'शनिवार', 'रविवार']
export const WEEKDAYS_EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const MONTHS_HI = ['जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर']
const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2025-08-25" → "25 अगस्त" (SPEC §13.4 "Dates hi"). */
export function dateHi(isoDate: string): string {
  const [, month, day] = isoDate.split('-').map(Number)
  return `${day} ${MONTHS_HI[month - 1]}`
}

/** "2025-08-25" → "25 August". */
export function dateEn(isoDate: string): string {
  const [, month, day] = isoDate.split('-').map(Number)
  return `${day} ${MONTHS_EN[month - 1]}`
}

export const MSG = {
  areaPayoutIntro: (nameHi: string, nameEn: string, drop: number): Bilingual => ({
    hi: `${nameHi} जी, आज भारी बारिश से आपके इलाके की बिक्री ${drop}% गिरी।`,
    en: `${nameEn} ji, heavy rain cut your area's sales by ${drop}% today.`,
  }),
  payoutCard: { hi: 'आज के सेटलमेंट के साथ जमा', en: "Credited with today's settlement", badge: 'No claim needed' },
  instalmentPaused: (instalment: string): Bilingual => ({
    hi: `कल की ${instalment} की किस्त रोक दी गई है।`,
    en: `Tomorrow's ${instalment} instalment is paused.`,
  }),
  soundbox: (amount: string): Bilingual => ({
    hi: `Paytm par ${amount} prapt hue — Chhatri se`,
    en: `${amount} received on Paytm, from Chhatri`,
  }),
  checkinSilent: (nameHi: string): Bilingual => ({
    hi: `${nameHi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?`,
    en: 'Your shop has been closed since yesterday. Is everything okay?',
  }),
  askSlip: {
    hi: 'जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।',
    en: 'Get well soon. Please send one photo of the hospital slip.',
  } as Bilingual,
  personalPaid: (nameHi: string, nameEn: string, amount: string): Bilingual => ({
    hi: `${nameHi} जी, आपका दावा मंज़ूर है। ${amount} आज के सेटलमेंट के साथ जमा।`,
    en: `${nameEn} ji, your claim is approved. ${amount} credited with today's settlement.`,
  }),
  slipToHuman: {
    hi: 'धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।',
    en: "Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours.",
  } as Bilingual,
  slipUnreadable: {
    hi: 'धन्यवाद। पर्ची साफ़ नहीं पढ़ी जा सकी, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।',
    en: "Thank you. We couldn't read the slip clearly, so our team will check it. You'll hear back within 24 hours.",
  } as Bilingual,
  explainArea: (weekdayHi: string, weekdayEn: string, expected: string, drop: number): Bilingual => ({
    hi: `आपका आम ${weekdayHi}: ${expected}। आज आपके इलाके की बिक्री ${drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है।`,
    en: `Your usual ${weekdayEn}: ${expected}. Your area fell ${drop}%. Chhatri pays half the lost sales.`,
  }),
  disputeAck: {
    hi: 'ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।',
    en: "Okay, I'm sending this to our team. You'll hear back within 24 hours.",
  } as Bilingual,
  disputeAlreadyOpen: (caseId: string): Bilingual => ({
    hi: `आपका सवाल पहले से हमारी टीम के पास है। केस ${caseId} देखिए।`,
    en: `Your question is already with our team. See case ${caseId}.`,
  }),
  disputeNoPayout: {
    hi: 'हमारी टीम ने आपका सवाल देखा। आपके खाते में अभी कोई भुगतान नहीं हुआ है, इसलिए बदलने के लिए कोई रकम नहीं है। आपके दावों के ट्रैकर में कारण दिखता है।',
    en: 'Our team looked at your question. No payout has been made on your account yet, so there is no amount to change. Your claim tracker shows why.',
  } as Bilingual,
  caseChip: (caseId: string): Bilingual => ({ hi: null, en: `Sent to a claims officer · case ${caseId}` }),
  coverBlocked: (startsOn: string): Bilingual => ({
    hi: `नया कवर वेटिंग पीरियड के बाद शुरू होता है — ${dateHi(startsOn)} से। कल के अलर्ट पर यह लागू नहीं होगा।`,
    en: `New cover starts after the waiting period — from ${dateEn(startsOn)}. It won't apply to tomorrow's alert.`,
  }),
  coverLink: (firstPayment: string, perDay: string, url: string): Bilingual => ({
    hi: `आगे के लिए कवर लेना हो तो ${firstPayment} (${perDay}/दिन) यहाँ भरें: ${url}`,
    en: `To buy cover for later, pay ${firstPayment} (${perDay}/day) here: ${url}`,
  }),
  officerApproved: (nameHi: string, nameEn: string, amount: string): Bilingual => ({
    hi: `${nameHi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। ${amount} जमा।`,
    en: `${nameEn} ji, our team approved your claim. ${amount} credited.`,
  }),
  officerDeclined: (nameHi: string, nameEn: string, reasonHi: string, reasonEn: string): Bilingual => ({
    hi: `${nameHi} जी, हमारी टीम ने आपका दावा देखा। ${reasonHi}`,
    en: `${nameEn} ji, our team reviewed your claim. ${reasonEn}`,
  }),
  fallbackHelp: {
    hi: 'मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"।',
    en: 'I\'m Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger".',
  } as Bilingual,
} as const

/**
 * Strings of Ask Chhatri and voice (copy deck 8.2, 9, 9.2, 9.3 and 15.5, fs-05 section 13). Each row is
 * `key: [English, Hindi]`, quoted from the deck, so a row cannot lose its Hindi. Marathi arrives with N8 and falls
 * back to Hindi here, as everywhere in the app. This file is separate from `en.ts` so the screen's copy is one unit.
 */
import type { Lang } from '../lib/lang'

const ROWS = {
  // Screen (copy deck 9)
  'ask.title': ['Ask Chhatri', 'छतरी से पूछें'],
  'ask.placeholder': ['Ask about your cover, a claim or a payout', 'अपने कवर, दावे या भुगतान के बारे में पूछें'],
  'ask.scope': ['You can ask about your cover, your claims and your payouts.', 'आप अपने कवर, दावों और भुगतानों के बारे में पूछ सकते हैं।'],
  'ask.rules_decide': ['Chhatri explains. The rules decide every payout, not this assistant.', 'छतरी समझाती है। हर भुगतान का फ़ैसला नियम करते हैं, यह सहायक नहीं।'],
  'ask.btn.send': ['Send', 'भेजें'],
  'ask.btn.cancel': ['Cancel', 'रद्द करें'],
  'ask.thinking': ['Looking at your records…', 'आपका रिकॉर्ड देखा जा रहा है…'],
  'ask.elapsed': ['Still working… {seconds} seconds', 'अभी भी काम चल रहा है… {seconds} सेकंड'],
  'ask.suggest.title': ['You can ask', 'आप पूछ सकते हैं'],
  'ask.suggest.why': ['Why did I get this amount?', 'मुझे इतने पैसे क्यों मिले?'],
  'ask.suggest.bigger': ['My loss was bigger', 'मेरा नुकसान ज़्यादा हुआ'],
  'ask.suggest.covered': ['What is covered?', 'क्या कवर है?'],
  'ask.suggest.starts': ['When does my cover start?', 'मेरा कवर कब शुरू होता है?'],
  'ask.suggest.waiting': ['What is the waiting period?', 'वेटिंग पीरियड क्या है?'],
  'ask.suggest.question': ['How do I question a payout?', 'भुगतान पर सवाल कैसे उठाऊँ?'],
  'ask.suggest.instalment': ['What happens to my loan instalment?', 'मेरी लोन किस्त का क्या होता है?'],
  'ask.cites.policy': ['From the policy: {clauses}', 'पॉलिसी से: {clauses}'],
  'ask.based_on': ['Based on', 'इस आधार पर'],
  'ask.details': ['Details', 'ब्योरा'],
  'ask.details.provider': ['Answered by', 'जवाब किसने दिया'],
  'ask.details.model': ['Model', 'मॉडल'],
  'ask.details.time': ['Time', 'समय'],
  'ask.details.reason': ['Why a backup was used', 'बैकअप क्यों इस्तेमाल हुआ'],
  'ask.you': ['You', 'आप'],
  // Fixed lines (copy deck 9.2 and the built catalogue)
  ASK_HANDOFF: ["I don't have an answer to this question. You can ask our team.", 'इस सवाल का जवाब मेरे पास नहीं है। आप हमारी टीम से पूछ सकते हैं।'],
  ASK_SCAM_WARNING: [
    'Careful: Chhatri does not ask for your OTP, PIN or password in a chat or on a call, and charges no fee to pay a claim. If a message asks for these, or asks you to install an app, do not reply.',
    'सावधान: छतरी चैट या फ़ोन पर आपसे OTP, PIN या पासवर्ड नहीं माँगती, और दावे का पैसा देने के लिए कोई फ़ीस नहीं लेती। ऐसा संदेश आए, या कोई ऐप इंस्टॉल करने को कहे, तो जवाब न दें।',
  ],
  ASK_MENTION_CHIP: ['{value} — is that right?', '{value} — सही है?'],
  ASK_MENTION_WORDS: ['You said "{heard}". Please type the number.', 'आपने कहा: "{heard}"। कृपया संख्या लिखकर बताइए।'],
  ASK_TOO_LONG: ['Please keep the question shorter.', 'सवाल थोड़ा छोटा रखिए।'],
  ASK_VOICE_NOTICE: [
    'Your voice may be sent to a speech service (Sarvam or your browser) to be turned into text. Please use the sample sentences.',
    'आपकी आवाज़ को लिखने के लिए किसी स्पीच सेवा (Sarvam या आपका ब्राउज़र) को भेजा जा सकता है। कृपया नमूना वाक्य बोलिए।',
  ],
  ASK_OFFLINE: ['There is a connection problem. Please try again in a little while.', 'कनेक्शन में दिक्कत है। थोड़ी देर बाद फिर कोशिश कीजिए।'],
  FALLBACK_HELP: [
    "I'm Chhatri. You can ask: \"Why did I get this amount?\" or \"My loss was bigger\".",
    'मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"।',
  ],
  VOICE_UNCLEAR: ["Sorry, I couldn't hear that clearly. Please say it again or type it.", 'माफ़ कीजिए, आवाज़ साफ़ नहीं सुनाई दी। कृपया फिर से बोलिए या लिखकर भेजिए।'],
  // Scam banner (copy deck 9.3). `scam.report` stays hidden until the helpline and portal are checked (deck open item 3).
  'scam.title': ['Be careful. This looks like a scam.', 'सावधान। यह धोखाधड़ी जैसा लग रहा है।'],
  'scam.do': [
    'Do not tap its link. Chhatri sends a payment link when you ask to buy cover, not before.',
    'उसके लिंक पर टैप न करें। छतरी भुगतान लिंक तब भेजती है जब आप कवर खरीदने को कहते हैं, उससे पहले नहीं।',
  ],
  'scam.note': ['This is a quick check of the words in the message. It can be wrong. If you are unsure, do not act on it.', 'यह संदेश के शब्दों की एक त्वरित जाँच है। यह ग़लत भी हो सकती है। शक हो, तो उस पर कुछ न करें।'],
  // Next action (copy deck 8.2)
  'next_action.SEE_CLAIM': ['See my claim', 'मेरा दावा देखें'],
  'next_action.SEE_COVER': ['See my cover', 'मेरा कवर देखें'],
  'next_action.GET_COVER': ['Get cover', 'कवर लें'],
  'next_action.SEND_SLIP': ['Send the slip photo', 'पर्ची की फ़ोटो भेजें'],
  'next_action.TRACK_CASE': ['Track my case', 'केस की स्थिति देखें'],
  'next_action.OPEN_CONSENTS': ['See my consents', 'मेरी सहमति देखें'],
  'next_action.TALK_TO_TEAM': ['Talk to the team', 'टीम से बात करें'],
  'next_action.ASK_AGAIN': ['Ask another question', 'दूसरा सवाल पूछें'],
  // Label reasons (copy deck 15.5)
  'fb.ask': ['Ask Chhatri is using ready-made answers right now.', 'अभी "छतरी से पूछें" में तैयार जवाब इस्तेमाल हो रहे हैं।'],
  'fb.reason.NO_KEY': ['No key is set for this service, so the built-in demo is used.', 'इस सेवा के लिए कोई की सेट नहीं है, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है।'],
  'fb.reason.MODEL_NOT_SET': ['A key is set but no model is chosen, so the built-in demo is used.', 'की सेट है पर मॉडल चुना नहीं गया है, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है।'],
  'fb.reason.FORCED': ['A presenter switched this on for the demo.', 'प्रस्तुतकर्ता ने डेमो के लिए इसे चालू किया है।'],
  'fb.reason.MOCK_BACKEND': ['This is the static demo, so recorded samples are shown.', 'यह स्टैटिक डेमो है, इसलिए रिकॉर्ड किए हुए नमूने दिख रहे हैं।'],
  'fb.reason.FREE_TIER_BLOCKED': ['Real data is not sent to a free service, so the built-in demo is used.', 'असली डेटा मुफ़्त सेवा को नहीं भेजा जाता, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है।'],
  'fb.reason.TIMEOUT': ['The service took too long to answer.', 'सेवा ने जवाब देने में बहुत समय लिया।'],
  'fb.reason.RATE_LIMITED': ['The service is busy or its free limit is used up.', 'सेवा व्यस्त है या उसकी मुफ़्त सीमा पूरी हो चुकी है।'],
  'fb.reason.PROVIDER_ERROR': ['The service returned an error.', 'सेवा से त्रुटि मिली।'],
  'fb.reason.INVALID_REPLY': ["The service's answer could not be used.", 'सेवा का जवाब इस्तेमाल करने लायक़ नहीं था।'],
  'fb.reason.GUARD_BLOCKED': ['The answer could not be matched with your records, so a fixed answer is shown.', 'जवाब आपके रिकॉर्ड से मिलाया नहीं जा सका, इसलिए तय जवाब दिखाया जा रहा है।'],
  'fb.reason.INJECTION_SUSPECTED': ['A ready-made answer is shown.', 'तैयार जवाब दिखाया जा रहा है।'],
  // Voice (copy deck 9.4)
  'voice.btn.speak': ['Speak', 'बोलिए'],
  'voice.btn.stop': ['Stop', 'रोकें'],
  'voice.btn.listen': ['Listen', 'सुनें'],
  'voice.state.idle': ['Tap the mic and speak.', 'माइक दबाकर बोलिए।'],
  'voice.state.listening': ['Listening… {seconds} of {max_seconds} seconds. Tap to stop.', 'सुन रहे हैं… {max_seconds} में से {seconds} सेकंड। रोकने के लिए टैप करें।'],
  'voice.state.processing': ['Understanding what you said…', 'आपकी बात समझी जा रही है…'],
  'voice.state.speaking': ['Playing the answer. Tap to stop.', 'जवाब सुनाया जा रहा है। रोकने के लिए टैप करें।'],
  'voice.err.denied': ['Microphone permission denied or unavailable', 'माइक की अनुमति नहीं मिली या माइक उपलब्ध नहीं है'],
  'voice.err.unsupported': ['This browser cannot record audio', 'यह ब्राउज़र आवाज़ रिकॉर्ड नहीं कर सकता'],
  'voice.err.fix': ['Allow the microphone in your browser settings, or type your message instead.', 'ब्राउज़र की सेटिंग में माइक की अनुमति दें, या अपना संदेश लिखकर भेजें।'],
  'voice.err.too_long': ['That was longer than {max_seconds} seconds. Please say it again, shorter.', 'यह {max_seconds} सेकंड से लंबा था। कृपया छोटा करके फिर से बोलिए।'],
  'voice.state.fallback': ['Voice is not available right now. You can type, or tap one of the ready questions.', 'अभी आवाज़ की सुविधा उपलब्ध नहीं है। आप लिख सकते हैं, या तैयार सवालों में से किसी पर टैप कर सकते हैं।'],
  'voice.sim.note': ['SIMULATED voice. The words come from the ready-made voice notes.', 'SIMULATED आवाज़। शब्द तैयार वॉइस नोट से आते हैं।'],
  'voice.transcript.label': ['What we heard. You can change it.', 'हमने यह सुना। आप इसे बदल सकते हैं।'],
  'voice.confirm.intro': ['Check each amount and date. Then send.', 'हर रकम और तारीख़ देखिए। फिर भेजिए।'],
  'voice.chip.right': ['Right', 'सही है'],
  'voice.chip.change': ['Change', 'बदलें'],
  'voice.chip.confirmed': ['Confirmed', 'पुष्टि हो गई'],
  'voice.chip.kal.ask': ['Did you mean yesterday or tomorrow?', 'आपका मतलब बीता हुआ कल था या आने वाला कल?'],
  'voice.chip.kal.yesterday': ['Yesterday', 'बीता हुआ कल'],
  'voice.chip.kal.tomorrow': ['Tomorrow', 'आने वाला कल'],
  'voice.send.hint': ['Confirm each amount and date to send.', 'भेजने के लिए हर रकम और तारीख़ की पुष्टि करें।'],
  'voice.confirm.rule': ['An amount or a date is used only after you confirm it.', 'कोई रकम या तारीख़ तभी इस्तेमाल होती है जब आप उसकी पुष्टि कर दें।'],
} as const satisfies Record<string, readonly [string, string]>

export type AskCopyKey = keyof typeof ROWS
export type AskCopyParams = Readonly<Record<string, string | number>>

const PLACEHOLDER = /\{(\w+)\}/g

/** `ta(key, lang, params)`: Hindi for `hi` and `mr` (Marathi is not shipped yet), English for `en`. A missing {name} stays visible. */
export function ta(key: AskCopyKey, lang: Lang, params: AskCopyParams = {}): string {
  const [en, hi] = ROWS[key]
  return (lang === 'en' ? en : hi).replace(PLACEHOLDER, (whole, name: string) => (name in params ? String(params[name]) : whole))
}

export const ASK_COPY_KEYS = Object.keys(ROWS) as AskCopyKey[]

/** A label reason with a line in the deck, or null (the screen then shows the code alone). */
export function reasonKey(reason: string): AskCopyKey | null {
  const key = `fb.reason.${reason}`
  return key in ROWS ? (key as AskCopyKey) : null
}

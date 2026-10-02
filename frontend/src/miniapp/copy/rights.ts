/**
 * Strings of the complaints ladder (N5, copy deck 13), the consent centre, the activity log and "forget my slip"
 * (N6, copy deck 14.4 to 14.6). Each row is `key: [English, Hindi]`, quoted from the deck, so a row cannot lose its
 * Hindi. Marathi arrives with N8 and falls back to Hindi, as everywhere in the app. The wording of the purposes
 * themselves (label, what is used, the effect of turning one off) comes from the API's notice module, not from here.
 * Rows marked "proposed" are not in the deck yet (screens-and-flows 7.1 names them as proposed buttons).
 */
import type { Lang } from '../lib/lang'

const ROWS = {
  // Complaints and escalation (copy deck 13.1)
  'grv.intro': [
    'If you are not happy with an answer, you can take a complaint up one step at a time. Each step shows its reply time, or says that it is not confirmed yet.',
    'अगर आप किसी जवाब से संतुष्ट नहीं हैं, तो शिकायत को एक-एक कदम ऊपर ले जा सकते हैं। हर कदम के साथ जवाब का समय दिखता है, या लिखा होता है कि वह अभी तय नहीं है।',
  ],
  'grv.step.PAYTM_DISPUTE': ['Our claims officer', 'हमारा क्लेम अधिकारी'],
  'grv.step.INSURER_GRO': ["The insurer's grievance officer", 'बीमा कंपनी का शिकायत अधिकारी'],
  'grv.step.BIMA_BHAROSA': ['IRDAI Bima Bharosa portal', 'IRDAI का बीमा भरोसा पोर्टल'],
  'grv.step.OMBUDSMAN': ['Insurance Ombudsman', 'बीमा लोकपाल'],
  'grv.step.LENDER_GRIEVANCE': ["The lender's grievance officer", 'लेंडर का शिकायत अधिकारी'],
  'grv.step.PAYTM_SUPPORT': ['Paytm support', 'Paytm सपोर्ट'],
  'grv.what.PAYTM_DISPUTE': ["A person in Chhatri's team looks at the numbers again.", 'छतरी की टीम का एक व्यक्ति आँकड़े दोबारा देखता है।'],
  'grv.what.INSURER_GRO': ["The insurer's officer for complaints looks at it.", 'बीमा कंपनी का शिकायतों का अधिकारी इसे देखता है।'],
  'grv.what.BIMA_BHAROSA': ['IRDAI, the insurance regulator, runs an online portal for complaints.', 'बीमा नियामक IRDAI शिकायतों के लिए एक ऑनलाइन पोर्टल चलाता है।'],
  'grv.what.OMBUDSMAN': [
    'An official set up under the Insurance Ombudsman Rules to settle insurance complaints. It is free for you.',
    'बीमा लोकपाल नियमों के तहत बना एक अधिकारी, जो बीमा की शिकायतें सुलझाता है। यह आपके लिए मुफ़्त है।',
  ],
  'grv.what.LENDER_GRIEVANCE': ["The lender's own officer for complaints about an instalment.", 'लेंडर का अपना अधिकारी, जो किस्त की शिकायतें देखता है।'],
  'grv.what.PAYTM_SUPPORT': ["Paytm's support team for payments, the app and your data.", 'Paytm की सपोर्ट टीम, जो पेमेंट, ऐप और आपके डेटा के सवाल देखती है।'],
  'grv.state.here': ['You are here', 'आप यहाँ हैं'],
  'grv.state.next': ['Next step', 'अगला कदम'],
  'grv.state.done': ['Done', 'हो गया'],
  'grv.state.locked': ['Opens after the step before', 'पिछले कदम के बाद खुलता है'],
  'grv.when_next': [
    'You can go to the next step if the answer does not settle it, or if the reply time has passed.',
    'जवाब से बात न सुलझे, या जवाब का समय निकल जाए, तो आप अगले कदम पर जा सकते हैं।',
  ],
  'grv.outside': [
    'Steps outside Chhatri are shown so that you know where to go. In this demo nothing is sent to them.',
    'छतरी के बाहर के कदम इसलिए दिखाए गए हैं ताकि आपको पता रहे कि कहाँ जाना है। इस डेमो में उन्हें कुछ नहीं भेजा जाता।',
  ],
  'grv.case': ['Case {case_id}', 'केस {case_id}'],
  'grv.contact.placeholder': [
    'Contact details come from the partner. This is a placeholder in the demo.',
    'संपर्क का ब्योरा साझेदार से आएगा। डेमो में यह सिर्फ़ एक नमूना है।',
  ],
  'grv.bring': ['Keep these ready: decision {decision_id} and case {case_id}.', 'ये तैयार रखें: फ़ैसला {decision_id} और केस {case_id}।'],
  'grv.filed.label': ['The date you filed', 'आपने किस तारीख़ को शिकायत की'],
  'grv.delivery.SELF_REPORTED': ['You file this yourself and tell us the date.', 'यह शिकायत आप ख़ुद करते हैं और हमें तारीख़ बताते हैं।'],
  'grv.delivery.SIMULATED': ['SIMULATED in this demo. Nothing is sent.', 'इस डेमो में SIMULATED। कुछ भेजा नहीं जाता।'],
  'grv.clock.own': ['We reply within {sla_hours} hours.', 'हम {sla_hours} घंटे में जवाब देते हैं।'],
  'grv.clock.confirm.insurer': ['Response time to be confirmed with the insurer.', 'जवाब का समय बीमा कंपनी से पूछकर तय होगा।'],
  'grv.clock.confirm.lender': ['Response time to be confirmed with the lender.', 'जवाब का समय लेंडर से पूछकर तय होगा।'],
  'grv.clock.confirm.paytm': ['Response time to be confirmed.', 'जवाब का समय अभी तय नहीं है।'],
  'grv.clock.portal': ['The portal says complaints are attended within {days} days.', 'पोर्टल के अनुसार शिकायतों पर {days} दिन के अंदर ध्यान दिया जाता है।'],
  'grv.state.PAYTM_DISPUTE.running': [
    'Our claims officer is looking at this. Answer due in {time_left}.',
    'हमारे क्लेम अधिकारी इसे देख रहे हैं। जवाब {time_left} में आना है।',
  ],
  'grv.state.PAYTM_DISPUTE.answered': [
    'Answered: the decision stands. You can read the numbers again in your receipt.',
    'जवाब दिया गया: फ़ैसला वही रहेगा। आप अपनी रसीद में आँकड़े फिर से देख सकते हैं।',
  ],
  'grv.state.PAYTM_DISPUTE.overdue': ['This is past our {sla_hours}-hour answer time.', 'यह हमारे {sla_hours} घंटे के जवाब के समय से आगे निकल गया है।'],
  'grv.state.INSURER_GRO.active': [
    "Sent to the insurer's grievance officer (SIMULATED in this demo). Response time to be confirmed with the insurer.",
    'बीमा कंपनी के शिकायत अधिकारी को भेजा गया (इस डेमो में SIMULATED)। जवाब का समय बीमा कंपनी से पूछकर तय होगा।',
  ],
  'grv.state.BIMA_BHAROSA.active': [
    'You filed on {date}. The portal says complaints are attended within {days} days. Day {n} of {days}.',
    'आपने {date} को शिकायत की। पोर्टल के अनुसार शिकायतों पर {days} दिन के अंदर ध्यान दिया जाता है। {days} में से दिन {n}।',
  ],
  'grv.state.BIMA_BHAROSA.past': ["The portal's stated {days} days have passed.", 'पोर्टल के बताए {days} दिन बीत चुके हैं।'],
  'grv.state.OMBUDSMAN.active': [
    'The Insurance Ombudsman service is free. No response time is stated.',
    'बीमा लोकपाल की सेवा मुफ़्त है। जवाब का कोई समय नहीं बताया गया है।',
  ],
  'grv.state.LENDER_GRIEVANCE.active': [
    "This is the lender's decision. Your request and the lender's answer are in your receipt. Response time to be confirmed with the lender.",
    'यह लेंडर का फ़ैसला है। आपका अनुरोध और लेंडर का जवाब आपकी रसीद में हैं। जवाब का समय लेंडर से पूछकर तय होगा।',
  ],
  'grv.state.PAYTM_SUPPORT.active': ['With Paytm support. Response time to be confirmed.', 'Paytm सपोर्ट के पास है। जवाब का समय अभी तय नहीं है।'],
  'grv.btn.to_gro': ["Send this to the insurer's grievance officer", 'इसे बीमा कंपनी के शिकायत अधिकारी को भेजें'],
  'grv.btn.to_bharosa': ['Complain on the Bima Bharosa portal', 'बीमा भरोसा पोर्टल पर शिकायत करें'],
  'grv.btn.to_ombudsman': ['Approach the Insurance Ombudsman', 'बीमा लोकपाल के पास जाएँ'],
  'grv.btn.resolved': ['Mark as solved', 'सुलझा हुआ मानें'],
  'grv.btn.how': ['How to file', 'शिकायत कैसे करें'],
  // Respondent router (copy deck 13.2)
  'grv.topic.title': ['What is your complaint about?', 'आपकी शिकायत किस बारे में है?'],
  'grv.topic.PAYOUT_AMOUNT': ['The amount of a payout', 'भुगतान की रकम'],
  'grv.topic.CLAIM_DECLINED': ['A claim that was not paid', 'जिस दावे का भुगतान नहीं हुआ'],
  'grv.topic.CLAIM_SLOW': ['A claim that is taking long', 'जिस दावे में देर हो रही है'],
  'grv.topic.EDI_HOLIDAY': ['My loan instalment', 'मेरी लोन किस्त'],
  'grv.topic.PAYMENT_NOT_RECEIVED': ['Money did not reach me', 'पैसे मुझ तक नहीं पहुँचे'],
  'grv.topic.PREMIUM_CHARGE': ['A premium charge', 'प्रीमियम की कटौती'],
  'grv.topic.DATA_OR_CONSENT': ['My data or my consent', 'मेरा डेटा या मेरी सहमति'],
  'grv.topic.APP_ISSUE': ['A problem with the app', 'ऐप में कोई समस्या'],
  'grv.topic.OTHER': ['Something else', 'कुछ और'],
  'grv.who.INSURER': ['This goes to the insurer. Our claims officer looks first.', 'यह बीमा कंपनी के पास जाता है। पहले हमारा क्लेम अधिकारी देखता है।'],
  'grv.who.LENDER': ['This goes to your lender.', 'यह आपके लेंडर के पास जाता है।'],
  'grv.who.PAYTM': ['This goes to Paytm support.', 'यह Paytm सपोर्ट के पास जाता है।'],
  'grv.text.label': ['Tell us in your own words', 'अपने शब्दों में बताइए'],
  'grv.btn.submit': ['Send', 'भेजें'],
  'grv.router.note': ['This is a guide. If you are not sure, choose Something else.', 'यह एक मार्गदर्शक है। समझ न आए, तो कुछ और चुनें।'],
  'empty.grievances': ['You have no open questions or complaints.', 'आपका कोई सवाल या शिकायत खुली नहीं है।'],
  // Proposed (screens-and-flows 7.1: the button that opens the form and the one that saves the filing date)
  'grv.time.hour': ['{n} hour', '{n} घंटा'],
  'grv.time.minute': ['{n} minute', '{n} मिनट'],
  'grv.time.hours': ['{n} hours', '{n} घंटे'],
  'grv.time.minutes': ['{n} minutes', '{n} मिनट'],
  'grv.new': ['New complaint', 'नई शिकायत'],
  'grv.btn.save_date': ['Save the date', 'तारीख़ सहेजें'],
  'grv.btn.close': ['Close', 'बंद करें'],
  'grv.solved': ['Marked as solved.', 'सुलझा हुआ मान लिया गया।'],
  'grv.sent': ['Your complaint is saved.', 'आपकी शिकायत दर्ज हो गई।'],
  'grv.error.conflict': ['This complaint has moved on. The list is updated.', 'यह शिकायत आगे बढ़ चुकी है। सूची नई कर दी गई है।'],
  'grv.portal': ['Portal: bimabharosa.irdai.gov.in', 'पोर्टल: bimabharosa.irdai.gov.in'],
  'grv.day_of': ['Day {n} of {days}', '{days} में से दिन {n}'],
  'grv.resolved': ['Solved', 'सुलझा'],
  'nba.grievances.open': ['Your case is with a claims officer. You will hear back within {sla_hours} hours.', 'आपका केस क्लेम अधिकारी के पास है। {sla_hours} घंटे में जवाब मिलेगा।'],
  'nba.grievances.new': ['Something is wrong? Tell us.', 'कुछ गड़बड़ है? हमें बताइए।'],
  'nba.grievances.new.btn': ['New complaint', 'नई शिकायत'],
  // Consent centre (copy deck 14.4)
  'consent.intro': ['You decide how Chhatri uses your data. You can turn each item off.', 'आप तय करते हैं कि छतरी आपके डेटा का कैसे इस्तेमाल करे। आप हर एक को बंद कर सकते हैं।'],
  'consent.version': ['Notice {version}. Prototype: nothing here is real data.', 'सूचना {version}। प्रोटोटाइप: यहाँ कुछ भी असली डेटा नहीं है।'],
  'consent.state.on': ['On', 'चालू'],
  'consent.state.off': ['Off', 'बंद'],
  'consent.state.not_given': ['Not given', 'दी नहीं गई'],
  'consent.source.seeded': ['Set up by the simulator for this demo.', 'इस डेमो के लिए सिमुलेटर ने बनाया।'],
  'consent.source.payment_app': ['Agreed when you paid, in the app.', 'भुगतान के समय ऐप में सहमति दी।'],
  'consent.source.payment_chat': ['Agreed when you paid, from the chat notice.', 'भुगतान के समय चैट की सूचना पर सहमति दी।'],
  'consent.source.slip_upload': ['Agreed when you sent a slip.', 'पर्ची भेजते समय सहमति दी।'],
  'consent.granted_on': ['Agreed on {date}', '{date} को सहमति दी'],
  'consent.used': ['What we use', 'हम क्या इस्तेमाल करते हैं'],
  'consent.receipt': ['Receipt', 'रसीद'],
  'consent.empty': ['You have not agreed to anything yet. You agree when you buy cover.', 'आपने अभी किसी बात पर सहमति नहीं दी है। कवर खरीदते समय आप सहमति देते हैं।'],
  'consent.withdraw.title': ['Turn this off?', 'इसे बंद करें?'],
  'consent.withdraw.confirm': ['Turn off', 'बंद करें'],
  'consent.withdraw.cancel': ['Keep it on', 'चालू रखें'],
  'consent.withdraw.done': ['Turned off.', 'बंद कर दिया।'],
  'consent.err.case_open': [
    'Your claim is still being checked by our team. You can turn this off once it is answered.',
    'आपका दावा अभी हमारी टीम देख रही है। जवाब आने के बाद आप इसे बंद कर सकते हैं।',
  ],
  'consent.err.already_withdrawn': ['This was already turned off. The list is updated.', 'यह पहले ही बंद हो चुका है। सूची नई कर दी गई है।'],
  'consent.activity_link': ['See what was used', 'देखें क्या इस्तेमाल हुआ'],
  'consent.complain': ['Complain about my data', 'मेरे डेटा के बारे में शिकायत करें'],
  'consent.switch': ['Switch: {label}', 'स्विच: {label}'],
  'nba.get_cover_from_consents': ['You agree to these when you buy cover.', 'कवर खरीदते समय आप इन पर सहमति देते हैं।'],
  'nba.get_cover_from_consents.btn': ['Get cover', 'कवर लें'],
  'nba.see_activity': ['See what was used, and when.', 'देखिए कब क्या इस्तेमाल हुआ।'],
  'nba.see_activity.btn': ['See what was used', 'देखें क्या इस्तेमाल हुआ'],
  'nba.back_to_consents': ['That is what was used so far.', 'अब तक यही इस्तेमाल हुआ है।'],
  'nba.back_to_consents.btn': ['My data and consent', 'मेरा डेटा और सहमति'],
  // Activity log (copy deck 14.5)
  'activity.empty': ['Nothing has been used yet.', 'अभी तक कुछ इस्तेमाल नहीं हुआ।'],
  'activity.chip.all': ['All', 'सभी'],
  'activity.chip.sales': ['Sales', 'बिक्री'],
  'activity.chip.slip': ['Slip', 'पर्ची'],
  'activity.chip.settlement': ['Premium', 'प्रीमियम'],
  'activity.more': ['Show more', 'और दिखाएँ'],
  'activity.times': ['Times are simulated.', 'समय सिमुलेटेड हैं।'],
  'receipt.check_log': ['Check the log', 'लॉग जाँचें'],
  'activity.log_ok': ['The log checks out: {entries} entries, none changed.', 'लॉग सही निकला: {entries} प्रविष्टियाँ, कोई नहीं बदली।'],
  'activity.log_bad': ['The log does not check out from entry {seq}.', 'लॉग प्रविष्टि {seq} से सही नहीं निकला।'],
  // Forget my slip (copy deck 14.6)
  'slip.held': ['Slip received {date}', '{date} को मिली पर्ची'],
  'slip.state.held': ['Held', 'रखी है'],
  'slip.state.erased': ['Erased', 'मिटाई गई'],
  'slip.erase': ['Erase this slip', 'यह पर्ची मिटाएँ'],
  'slip.erase.blocked': ['Your claim is still being checked. You can erase the slip once it is answered.', 'आपका दावा अभी जाँचा जा रहा है। जवाब आने के बाद आप पर्ची मिटा सकते हैं।'],
  'slip.erase.title': ['Erase this slip?', 'यह पर्ची मिटाएँ?'],
  'slip.erase.removes': [
    'We will erase: the photo, the details read from it (name, dates, hospital), and the same text in your claim record.',
    'हम मिटाएँगे: फ़ोटो, उससे पढ़ी गई जानकारी (नाम, तारीख़ें, अस्पताल), और आपके दावे के रिकॉर्ड में वही लिखा हुआ।',
  ],
  'slip.erase.keeps': ['We will keep: the decision, the amount, and which checks passed or failed.', 'हम रखेंगे: फ़ैसला, रकम, और कौन-सी जाँच पास या फ़ेल हुई।'],
  'slip.erase.audit_note': [
    'The activity log cannot be edited, so it can still show the name and dates from this slip in entries written before today.',
    'गतिविधि का लॉग बदला नहीं जा सकता, इसलिए आज से पहले लिखी गई प्रविष्टियों में इस पर्ची का नाम और तारीख़ें दिख सकती हैं।',
  ],
  'slip.erase.confirm': ['Erase', 'मिटाएँ'],
  'slip.erase.cancel': ['Keep it', 'रहने दें'],
  'slip.erase.done': ['Slip erased.', 'पर्ची मिटा दी गई।'],
  'slip.erase.err.already_erased': ['This slip was already erased. The list is updated.', 'यह पर्ची पहले ही मिटाई जा चुकी है। सूची नई कर दी गई है।'],
} as const satisfies Record<string, readonly [string, string]>

export type RightsCopyKey = keyof typeof ROWS
export type RightsCopyParams = Readonly<Record<string, string | number>>

const PLACEHOLDER = /\{(\w+)\}/g

/** `tr(key, lang, params)`: Hindi for `hi` and `mr` (Marathi is not shipped yet), English for `en`. A missing {name} stays visible. */
export function tr(key: RightsCopyKey, lang: Lang, params: RightsCopyParams = {}): string {
  const [en, hi] = ROWS[key]
  return (lang === 'en' ? en : hi).replace(PLACEHOLDER, (whole, name: string) => (name in params ? String(params[name]) : whole))
}

export const RIGHTS_COPY_KEYS = Object.keys(ROWS) as RightsCopyKey[]

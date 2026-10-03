/**
 * Copy of the landing page "/" that the deck content (content/deck.ts) does not already hold. Numbers are the SPEC
 * §17.2 golden numbers of the monsoon replay and the values in backend/chhatri/policy/rules.yaml; nothing here is
 * measured live, and every figure that comes from the replay or the backtest says so where it is shown.
 */
import type { IconName } from '../common/Icon'

/** The hero's three promises (the ticks under the buttons). */
export const PROMISES: readonly string[] = ['No claim form', 'Paid with the day’s settlement', 'Every rupee explained']

/** The proof strip under the hero: the monsoon replay at 17:05 (SPEC §17.2). */
export const REPLAY_FIGURES: readonly { value: string; label: string; count?: boolean }[] = [
  { value: 'Same day', label: 'from loss to money, against 30–60 days before' },
  { value: '4 min', label: 'from the trigger to the credit', count: true },
  { value: '312', label: 'shops paid in the storm replay', count: true },
  { value: '0', label: 'claim forms or documents' },
]
export const REPLAY_CAPTION = 'Monsoon replay of 19 Aug 2025: real rainfall, simulated sales. Not production results.'

export type Step = { title: string; text: string; icon: IconName }
/** How it works: the four verbs of the product. */
export const STEPS: readonly Step[] = [
  { title: 'Detect', icon: 'map', text: 'A model expects every shop’s sales hour by hour. During an official alert, a whole area falling far below expected is a real loss.' },
  { title: 'Decide', icon: 'shield', text: 'A published rule set checks the cover, the waiting period, the area index and the daily cap. Code decides, not AI.' },
  { title: 'Pay', icon: 'bolt', text: 'The payout is credited with that day’s Paytm settlement, and the Soundbox says it out loud.' },
  { title: 'Protect', icon: 'pause', text: 'The lender is asked to pause the next loan instalment, so a bad day doesn’t turn into a missed payment.' },
]

/** The two ways a claim starts (deck TWO_WAYS, shortened for cards). */
export const STARTS: readonly { title: string; when: string; merchant: string; check: string }[] = [
  { title: 'Area shock · rain, heatwave, bandh', when: 'An alert is out and the area’s sales stay below half of expected for 3 hours', merchant: 'Nothing', check: 'An index of at least 20 shops, so one shop can’t fake it' },
  { title: 'Personal shock · illness, accident', when: 'A shop’s payments stop for a full business day', merchant: 'One voice reply and one photo of the hospital slip', check: 'The slip’s name matches KYC and its dates match the silent days' },
]

export type Lane = { key: 'ai' | 'rules' | 'paytm'; verb: string; title: string; items: readonly string[]; note: string }
/** "AI understands. Rules decide. Paytm executes." */
export const LANES: readonly Lane[] = [
  {
    key: 'ai',
    verb: 'AI understands',
    title: 'Language and documents',
    items: ['Hears Hindi and Marathi voice notes', 'Reads the hospital slip', 'Answers “why this amount?” from the policy, with clause numbers', 'Spots scam and prompt-injection messages'],
    note: 'Gemini or Sarvam when keys are set; written templates when not.',
  },
  {
    key: 'rules',
    verb: 'Rules decide',
    title: 'The policy engine',
    items: ['The only part that can say APPROVED', 'Same facts in, same decision out', 'Lists every check and clause it used', 'Sends anything uncertain to a claims officer'],
    note: 'Deterministic code with a published rule set (pilot-0.1).',
  },
  {
    key: 'paytm',
    verb: 'Paytm executes',
    title: 'Money and messages',
    items: ['Credits the payout with the settlement', 'Announces it on the Soundbox', 'Asks the lender to pause the instalment', 'Tells the merchant on WhatsApp or Telegram'],
    note: 'Simulated in the prototype; the Telegram bot can run live.',
  },
]
export const BOUNDARY_LABEL = 'AI cannot approve money'

export type JourneyStep = { at: string; text: string; asset: string; paytm: boolean }
/** Why Paytm: the storm replay as one Paytm-native journey (SPEC §17.2 times). */
export const PAYTM_JOURNEY: readonly JourneyStep[] = [
  { at: '14:00', text: 'Red alert over Parel · Lalbaug', asset: 'Weather alert', paytm: false },
  { at: '14:00–17:00', text: '46 shops’ sales hold at 37% of expected', asset: 'Paytm payments data', paytm: true },
  { at: '17:00', text: 'The trigger fires; the rules approve 46 claims', asset: 'Chhatri rules', paytm: false },
  { at: '17:04', text: '₹1,380 credited to Anil with the day’s settlement', asset: 'Paytm settlement', paytm: true },
  { at: '17:04', text: '“Paytm par ₹1,380 prapt hue — Chhatri se”', asset: 'Paytm Soundbox', paytm: true },
  { at: '17:05', text: 'Tomorrow’s ₹600 instalment paused', asset: 'Paytm merchant loan', paytm: true },
]

export type Feature = { title: string; text: string; icon: IconName | null; glyph?: string }
export const FEATURES: readonly Feature[] = [
  { title: 'Starts by itself', icon: 'bolt', text: 'No form and no call. The claim starts from the area’s sales and the alert.' },
  { title: 'Paid the same day', icon: null, glyph: '₹', text: 'Credited with the evening settlement, four minutes after the trigger in the replay.' },
  { title: 'Instalment paused', icon: 'pause', text: 'The lender is asked to move the next loan instalment to the end of the loan.' },
  { title: 'Every rupee explained', icon: 'question', text: '“Why ₹1,380?” shows the sum: half of the usual day × the area’s drop.' },
  { title: 'In the merchant’s language', icon: 'mic', text: 'Hindi, English and Marathi, typed or spoken, on WhatsApp or Telegram.' },
  { title: 'Illness in one photo', icon: 'camera', text: 'A hospital slip is checked against KYC and the silent days before any money moves.' },
  { title: 'Hard to fake', icon: 'map', text: 'An area index of at least 20 shops, an official alert and a 7-day waiting period.' },
  { title: 'A receipt for every decision', icon: 'notes', text: 'Clauses, checks and a tamper-evident audit entry that anyone can verify.' },
]

export type Party = { party: string; gets: string; shows: string }
/** Who benefits. The pilot tests these; nobody has signed up. */
export const PARTIES: readonly Party[] = [
  { party: 'Merchant', gets: 'Income on the day it stops', shows: '₹1,380 the same evening and the next instalment paused' },
  { party: 'Insurer', gets: 'A new embedded product with priced, auditable claims', shows: 'Every decision follows published rules and is logged' },
  { party: 'Paytm', gets: 'Distribution revenue and merchants who stay', shows: 'A rider on the existing merchant plan, bought in three taps' },
  { party: 'Lender', gets: 'Fewer missed instalments on shock days', shows: 'A holiday request with the evidence attached' },
]
export const PARTIES_NOTE = 'These are what a pilot would test. No insurer, lender or Paytm team has signed anything; the prototype runs on simulated sales.'

export const PRICE = Object.freeze({
  range: '₹6.93 to ₹38.82',
  example: 'Z7, Anil’s area: ₹18.62 a day',
  note: 'Zone premiums from the backtest on simulated sales. Paytm’s existing merchant plan sells for under ₹2 a day, so the real price is the pilot’s main open question.',
})

export type Faq = { q: string; a: string }
export const FAQS: readonly Faq[] = [
  {
    q: 'Is Chhatri live with Paytm?',
    a: 'No. It is a prototype built for the Paytm Build for India AI Hackathon. Sales, alerts, KYC, payouts, the lender and the Soundbox are simulated and labelled as such. The rainfall history is real (Open-Meteo), and the AI providers and the Telegram bot can run live.',
  },
  {
    q: 'Can the AI approve a payout?',
    a: 'No. The AI hears voice notes, reads slips and explains decisions. Only the rules engine can approve money, and anything uncertain goes to a claims officer.',
  },
  {
    q: 'What stops a shop from faking a loss?',
    a: 'One shop can’t start an area payout: the index needs at least 20 shops, the drop must hold for 3 hours during an official alert, and new cover starts only after a 7-day waiting period. A personal claim needs a hospital slip whose name matches KYC and whose dates match the shop’s silent days.',
  },
  {
    q: 'How is the amount worked out?',
    a: 'Half of the shop’s usual day × the area’s drop, up to ₹2,500 a day. For Anil: ½ × ₹4,380 × 63% = ₹1,380. A hospital-cash day pays ₹1,500.',
  },
  {
    q: 'What does it cost a merchant?',
    a: 'In the backtest, zone premiums run from ₹6.93 to ₹38.82 a day. Paytm’s existing merchant plan sells for under ₹2 a day, so the price is the main question for a pilot.',
  },
  {
    q: 'What if the merchant disagrees?',
    a: 'They can ask for a person in the same chat. Every answer names the policy clause it rests on, and the grievance path goes on to the insurer, the IRDAI Bima Bharosa portal and the Insurance Ombudsman.',
  },
  {
    q: 'What data does Chhatri use?',
    a: 'Only what the merchant agreed to share: hourly sales, the payout account and, for a personal claim, one photo. Each consent can be seen and withdrawn in the app.',
  },
]

/** Footer link columns: the console's own pages. */
export const FOOTER_LINKS: readonly { title: string; links: readonly { to: string; label: string }[] }[] = [
  {
    title: 'Product',
    links: [
      { to: '/live', label: 'Live map' },
      { to: '/merchant/S-0142', label: 'Merchant phone' },
      { to: '/claims', label: 'Claims console' },
    ],
  },
  {
    title: 'Trust',
    links: [
      { to: '/audit', label: 'Audit log' },
      { to: '/backtest', label: 'Backtest' },
      { to: '/policy', label: 'Policy wording' },
    ],
  },
]

/**
 * Static story content for the Overview page, taken from the pitch deck (slides 1-13) and the
 * SPEC golden numbers (§0, §9.4, §13.6, §17.2). Everything live (backtest, integrations) is fetched;
 * only the deck's narrative and the fixed monsoon-replay story strings live here.
 */
import type { ScenarioName, VoiceDemoKey } from '../api/types'

export const TEAM = Object.freeze({ name: 'Da Goats', members: ['Omkar Kadam', 'Ujjwal Pardeshi'] as const, role: 'Full-stack engineer' })

export const DEMO_MERCHANT = 'S-0142'
export const COVER_MERCHANT = 'S-0907'

/** One step a launcher runs after loading and seeking (existing SPEC §19 phone endpoints). */
export type LaunchAction = { kind: 'voice'; merchant: string; key: VoiceDemoKey } | { kind: 'sample'; merchant: string; file: string }

/**
 * A scenario jump (SPEC §17.2, B5): load `scenario`, optionally seek to `seek`, run `actions`, open
 * `to` (with an optional `hint` for the page, e.g. which phone chip to highlight), then optionally
 * start playing at `play` simulated minutes per second so the story happens live on screen, and
 * pause again at `pauseAt` (HH:MM) once the story beat is over.
 */
export type Launch = {
  scenario: ScenarioName
  seek: string | null
  to: string
  play?: number
  pauseAt?: string
  actions?: readonly LaunchAction[]
  hint?: string
}

/** Replay speed for the "watch it happen" launchers: 17:00 trigger, 17:04 money, 17:05 pause in ~8 s. */
export const WATCH_SPEED = 1
/** The storm launchers start three simulated minutes before the 17:00 trigger. */
export const STORM_LEAD_IN = '16:57'
/** …and pause one minute after the 17:05 instalment pause, holding the whole storm on screen. */
export const STORM_BEAT_END = '17:06'

export const LAUNCHES = Object.freeze({
  storm: { scenario: 'monsoon', seek: '17:05', to: '/live' },
  stormLive: { scenario: 'monsoon', seek: STORM_LEAD_IN, to: '/live', play: WATCH_SPEED, pauseAt: STORM_BEAT_END },
  rainDay: { scenario: 'monsoon', seek: '17:02', to: `/merchant/${DEMO_MERCHANT}`, play: WATCH_SPEED, pauseAt: STORM_BEAT_END },
  questions: { scenario: 'monsoon', seek: '17:05', to: `/merchant/${DEMO_MERCHANT}`, hint: 'why' },
  illness: { scenario: 'illness', seek: '11:20', to: `/merchant/${DEMO_MERCHANT}`, hint: 'ill' },
  mismatch: { scenario: 'illness_mismatch', seek: '11:20', to: `/merchant/${DEMO_MERCHANT}`, hint: 'ill' },
  cover: { scenario: 'buy_cover', seek: '18:10', to: `/merchant/${COVER_MERCHANT}`, hint: 'cover' },
  reviewCase: {
    scenario: 'illness_mismatch',
    seek: '11:20',
    to: '/claims',
    actions: [
      { kind: 'voice', merchant: DEMO_MERCHANT, key: 'ill' },
      { kind: 'sample', merchant: DEMO_MERCHANT, file: 'mismatch_admission_slip.png' },
    ],
  },
} satisfies Record<string, Launch>)

export type LaunchKey = keyof typeof LAUNCHES

/** Deck slide 2: time to money after a loss, in days. */
export type TimeToMoney = { label: string; minDays: number; maxDays: number; text: string; ours: boolean }
export const TIME_TO_MONEY: readonly TimeToMoney[] = [
  { label: 'Paytm’s earlier merchant protection plans', minDays: 30, maxDays: 60, text: '30-60', ours: false },
  // SEWA: facts-and-sources §E says only "weeks"; minDays/maxDays only draw the bar (illustrative), the label does not claim a day range.
  { label: 'Weather-triggered heat cover (SEWA)', minDays: 42, maxDays: 56, text: 'Weeks', ours: false },
  { label: 'Chhatri', minDays: 0, maxDays: 0, text: 'Same day', ours: true },
]

export const FAILURES: readonly { what: string; evidence: string }[] = [
  { what: 'Claims are slow and need proof', evidence: 'Paytm’s earlier merchant plans took 30 to 60 days and needed multiple documents.' },
  { what: 'Weather readings miss real losses', evidence: 'Across 270 Indian weather-insurance contracts: a one-in-three chance of no payout even after a total crop loss.' },
  { what: 'Loan instalments don’t stop', evidence: 'Daily instalments are cut from settlements, even on the day sales collapse.' },
]

export const PROBLEM_SOURCES = 'Sources: Assurekit-Paytm case study; NPR, Jul 2025 (SEWA); Clarke et al. 2012, via Cornell NEUDC; Paytm Q1 FY27 results'

/** Deck slide 3: one bad day, two ways. */
export type TimelineStep = { at: string; text: string }
export const TYPICAL_DAY: readonly TimelineStep[] = [
  { at: 'Day 1', text: 'Heavy rain; sales fall 60%. The ₹600 loan instalment is still cut.' },
  { at: 'Day 2', text: 'Anil searches for the policy and the claim form.' },
  { at: 'Day 5', text: 'Uploads bills and photos; is asked for more.' },
  { at: 'Day 30-60', text: 'Claim decided, if the loss is covered at all.' },
]
export const CHHATRI_DAY: readonly TimelineStep[] = [
  { at: '14:00', text: 'Red alert; the area’s sales drop below the model’s expected range.' },
  { at: '17:00', text: 'The drop holds for 3 hours across 46 shops; the trigger fires.' },
  { at: '17:04', text: '₹1,380 credited with the settlement; the Soundbox announces it.' },
  { at: '17:05', text: 'Tomorrow’s ₹600 instalment paused automatically.' },
]

/** Deck slide 4: one engine, five steps, and a learning loop. */
export const ENGINE_STEPS: readonly { title: string; text: string; control: boolean }[] = [
  { title: 'Watch', text: 'Expected sales for every shop, hour by hour.', control: false },
  { title: 'Detect', text: 'An area drops during an alert, or one shop goes silent.', control: false },
  { title: 'Decide', text: 'Policy engine checks cover, amount and fraud signals.', control: true },
  { title: 'Pay', text: 'Same-day payout; loan instalment paused.', control: false },
  { title: 'Explain', text: 'Answers “why this amount” in the merchant’s language.', control: false },
]
export const LEARN_LOOP = 'Learn: every payout, dispute and review sharpens the triggers.'

export const TWO_WAYS: readonly { label: string; area: string; personal: string }[] = [
  { label: 'Starts when', area: 'A weather or civic alert, and the area’s sales fall far below expected', personal: 'A shop’s payments stop for a full business day' },
  { label: 'Merchant does', area: 'Nothing', personal: 'Replies to a voice check-in and sends one photo' },
  { label: 'Checked by', area: 'An area-level index, so one shop can’t fake it', personal: 'AI reads the slip; name matches KYC; dates match the silent days' },
  { label: 'Paid', area: 'Same day, automatically', personal: 'Same day; doubtful cases go to a human' },
]

/** SPEC §17.2 golden strings of the monsoon replay at 17:05 (deck slide 6). */
export const STORM = Object.freeze({
  when: 'Monsoon replay · Tue 19 Aug 2025 · 17:05',
  zone: { id: 'Z7', ward: 'F/S', name: 'Parel · Lalbaug', shops: 46 },
  rows: [
    { label: 'Alert', value: 'Red alert from 14:00' },
    { label: 'Sales', value: '37% of expected for 3 hours' },
    { label: 'Cover', value: '46 of 46 prepaid' },
    { label: 'Paid', value: '17:04, with the settlement' },
    { label: 'Total', value: '₹58,900 · instalments paused' },
  ] as const,
  zonesTriggered: 3,
  shopsPaid: 312,
  triggerToMoneyMin: 4,
  z9: 'Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That’s a slow day, not a loss event, so Chhatri doesn’t pay.',
})

/** SPEC §9.4 payout authority table (deck slide 8), exact wording. */
export const AUTHORITY: readonly { case: string; alone: string; human: string }[] = [
  { case: 'Area drop during an alert, index clear', alone: 'Pays', human: 'Only if the merchant disputes' },
  { case: 'Personal claim, slip matches name and dates', alone: 'Pays up to the daily cap', human: 'Anything above the cap' },
  { case: 'Slip unclear or dates don’t match', alone: 'Never', human: 'Always' },
  { case: 'Cover bought after an alert', alone: 'Never', human: 'Waiting period applies' },
]

export type LiveTest = { quote: string; tag: 'EXPLAINED' | 'HUMAN' | 'BLOCKED'; tone: 'blue' | 'amber' | 'red'; text: string; launch: LaunchKey }
/** SPEC §0 item 5, §13.6: the three live tests of deck slide 8. */
export const LIVE_TESTS: readonly LiveTest[] = [
  { quote: '“My loss was bigger than that.”', tag: 'EXPLAINED', tone: 'blue', text: 'Chhatri shows the numbers and offers a human review.', launch: 'questions' },
  { quote: 'A hospital slip with a different name', tag: 'HUMAN', tone: 'amber', text: 'No automatic payout. A claims officer decides.', launch: 'mismatch' },
  { quote: '“Red alert tomorrow. Cover me today.”', tag: 'BLOCKED', tone: 'red', text: 'New cover starts after the waiting period.', launch: 'cover' },
]

/** Deck slide 9: statistics measure the loss, AI talks to people, code controls the money. */
export const SIGNALS: readonly string[] = ['Hourly sales per shop', 'Weather and civic alerts', 'Merchant voice replies', 'Photos of hospital slips', 'Loan instalment schedule']
export const REASONING: readonly { title: string; text: string }[] = [
  { title: 'Expected-sales model', text: 'LightGBM per area and shop type. Pays only when sales fall below the bottom of its prediction range.' },
  { title: 'Sarvam chat + vision', text: 'Runs the conversation in the merchant’s language; a vision model reads the slip.' },
  { title: 'Cognee memory graph', text: 'Links shops, areas, past events, payouts and disputes.' },
]
export const CONTROL: readonly string[] = ['FastAPI service with cover rules, caps and the waiting period', 'Checks prepaid cover, the area index, KYC and dates', 'Writes the audit log']
export const ACTIONS: readonly { title: string; text: string }[] = [
  { title: 'n8n workflows', text: 'Payout, instalment pause, human review and follow-ups.' },
  { title: 'Paytm payment links', text: 'Premium paid through the Paytm MCP server (staging).' },
  { title: 'Sarvam voice', text: 'Bulbul speaks on WhatsApp and the Soundbox; Saaras hears code-mixed Hindi.' },
]
export const STACK: readonly string[] = ['Python + FastAPI', 'LightGBM', 'Sarvam: Bulbul, Saaras, chat', 'Cognee', 'n8n', 'Paytm MCP server', 'WhatsApp Cloud API', 'Open-Meteo', 'React + Leaflet']

/** Deck slide 13. */
export const ROADMAP: readonly { when: string; title: string; items: readonly string[] }[] = [
  {
    when: 'By 3 October',
    title: 'Hackathon final',
    items: ['Storm replay on a live city heat map', 'Personal claim on WhatsApp in Hindi: voice and one photo', 'Payout, instalment pause and audit log', 'Premium paid with a real Paytm link (staging)'],
  },
  {
    when: 'Before the next monsoon',
    title: 'Backtest and pilot',
    items: ['Replay two past monsoons on sandboxed sales data', 'Set triggers and prices with one insurer', 'Pilot with merchants already on the plan, in one city'],
  },
  { when: 'After the pilot', title: 'Scale', items: ['Heatwave and bandh cover', 'More cities and languages', 'Area income index for insurers through Pi'] },
]

/** The 10-second takeaway under the hero (SPEC §17.2 golden numbers, deck slide 3). */
export const HERO_FIGURES: readonly { value: string; label: string; count?: boolean }[] = [
  { value: '₹1,380', label: 'credited at 17:04' },
  { value: String(STORM.shopsPaid), label: 'shops paid', count: true },
  { value: `${STORM.triggerToMoneyMin} min`, label: 'trigger to money', count: true },
  { value: '0', label: 'forms or documents' },
]

/** Deck slide 12: why Paytm wins. Revenue in ₹ crore, value drivers and go-to-market, exact wording. */
export const BUSINESS = Object.freeze({
  title: 'Claims that start themselves grow insurance revenue and protect the loan book.',
  chartLabel: 'Paytm financial services revenue, ₹ crore',
  revenue: [
    { quarter: 'Q1 FY26', crore: 561, ours: false },
    { quarter: 'Q1 FY27', crore: 814, ours: true },
  ],
  growth: '+45% in a year.',
  growthNote: 'Insurance sits in this line, and it grows on merchants who stay active on Paytm.',
  drivers: [
    { driver: 'Insurance distribution', how: 'A rider on the existing merchant plan, sold in the same three taps' },
    { driver: 'Merchant renewals', how: 'Getting paid on a bad day is the best reason to renew' },
    { driver: 'Loan quality', how: 'On bad days, instalments are paused and covered instead of missed' },
    { driver: 'Data for Pi', how: 'A live area income index, offered to insurers and lenders' },
  ],
  goToMarket:
    'Start as a rider on Paytm’s merchant plan (2 lakh+ merchants) in one flood-prone city, with one insurer. Add heatwave cover for north India. Later, offer the area income index to insurers and lenders through Pi.',
  sources: 'Sources: Paytm Q1 FY27 results; Assurekit-Paytm case study; Insurance Act 1938, Sec. 64VB; Pi: Bloomberg via Free Press Journal, Sep 2026',
})

/**
 * What is real, what can be live, what is always simulated (SPEC §0.1). The live count comes from
 * GET /api/integrations at render time, never from this file.
 */
export const HONESTY_TIERS = Object.freeze({
  real: { title: 'Real code, always', text: 'Policy engine, audit log, claims console.' },
  keyed: { title: 'Live when keys are set', text: 'Sarvam, WhatsApp, Paytm link (staging), n8n, Cognee.' },
  simulated: { title: 'Always simulated and labelled', text: 'Sales, alerts, KYC, payouts, lender, Soundbox.' },
})

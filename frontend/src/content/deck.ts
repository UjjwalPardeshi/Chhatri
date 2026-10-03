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

/**
 * What is real, what can be live, what is always simulated (SPEC §0.1). The live count comes from
 * GET /api/integrations at render time, never from this file.
 */
export const HONESTY_TIERS = Object.freeze({
  real: { title: 'Real code, always', text: 'Policy engine, audit log, claims console.' },
  keyed: { title: 'Live when keys are set', text: 'Sarvam, WhatsApp, Paytm link (staging), n8n, Cognee.' },
  simulated: { title: 'Always simulated and labelled', text: 'Sales, alerts, KYC, payouts, lender, Soundbox.' },
})

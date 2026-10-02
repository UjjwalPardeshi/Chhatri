/**
 * The deck's WhatsApp conversations (slides 1 and 7) as SPEC §19.2 `Message` values, rendered by the
 * real phone components on the Overview page. Text comes from the §13.4 catalogue with the monsoon
 * and illness golden facts (§17.2): ₹4,380 usual Tuesday, 63% drop, ₹1,380 area payout, ₹600
 * instalment, ₹1,500 personal payout, case C-2291.
 */
import type { Message, MessageKind, PayoutCard } from '../api/types'
import { isFeatureEnabled } from '../features'
import { MSG, type Bilingual } from './catalogue'
import { DEMO_MERCHANT } from './deck'
import { HOLIDAY } from './holiday'

const MONSOON_DAY = '2025-08-19'
const ILLNESS_DAY = '2025-08-21'
const IST = '+05:30'

export const STORY = Object.freeze({
  nameHi: 'अनिल',
  nameEn: 'Anil',
  drop: 63,
  areaAmount: '₹1,380',
  usualDay: '₹4,380',
  instalment: '₹600',
  personalAmount: '₹1,500',
  caseId: 'C-2291',
})

type Spec = {
  id: string
  day: string
  at: string
  kind: MessageKind
  text?: Bilingual | null
  inbound?: boolean
  card?: PayoutCard
  media?: string
  seconds?: number
}

/** Voice notes carry the simulated-voice label and duration (SPEC §19.2 Message.meta). */
function metaFor(spec: Spec): Message['meta'] {
  if (spec.kind !== 'VOICE') return {}
  return { voice_source: 'browser-simulated', duration_s: spec.seconds, transcript: spec.text?.hi ?? undefined }
}

function message(spec: Spec): Message {
  return {
    id: spec.id,
    merchant_id: DEMO_MERCHANT,
    direction: spec.inbound ? 'INBOUND' : 'OUTBOUND',
    channel: spec.kind === 'SOUNDBOX' ? 'SOUNDBOX' : 'WHATSAPP',
    kind: spec.kind,
    text_hi: spec.text?.hi ?? null,
    text_en: spec.text?.en ?? null,
    audio_url: null,
    media_url: spec.media ?? null,
    card: spec.card ?? null,
    created_at: `${spec.day}T${spec.at}:00${IST}`,
    meta: metaFor(spec),
  }
}

function areaCard(): PayoutCard {
  return { amount_label: STORY.areaAmount, subtitle_hi: MSG.payoutCard.hi, subtitle_en: MSG.payoutCard.en, badge: MSG.payoutCard.badge }
}

/** SPEC §13.5 personal payout card; badge as the backend catalogue's PAYOUT_CARD_BADGE_PERSONAL. */
function personalCard(): PayoutCard {
  return { amount_label: STORY.personalAmount, subtitle_hi: MSG.payoutCard.hi, subtitle_en: MSG.payoutCard.en, badge: 'One photo, no forms' }
}

const WHY: Bilingual = { hi: 'मुझे इतने ही पैसे क्यों मिले?', en: 'Why did I get only this much?' }
const DISPUTE: Bilingual = { hi: 'मेरा नुकसान ज़्यादा हुआ।', en: 'My loss was bigger.' }
const ILL: Bilingual = { hi: 'मैं अस्पताल में हूँ, बुखार है।', en: 'I’m in hospital with a fever.' }

/** Deck slide 1: the whole idea on one screen (17:06). */
export const HERO_THREAD: readonly Message[] = [
  message({ id: 'h1', day: MONSOON_DAY, at: '17:04', kind: 'TEXT', text: MSG.areaPayoutIntro(STORY.nameHi, STORY.nameEn, STORY.drop) }),
  message({ id: 'h2', day: MONSOON_DAY, at: '17:04', kind: 'PAYOUT_CARD', card: areaCard() }),
  message({ id: 'h3', day: MONSOON_DAY, at: '17:05', kind: 'VOICE', inbound: true, text: WHY, seconds: 4 }),
  /** Deck slide 1 shows Chhatri's answer in English only, which keeps it clear of the Soundbox line. */
  message({ id: 'h4', day: MONSOON_DAY, at: '17:05', kind: 'TEXT', text: { hi: null, en: MSG.explainArea('मंगलवार', 'Tuesday', STORY.usualDay, STORY.drop).en } }),
]

export const RAIN_SOUNDBOX: Message = message({ id: 'r4', day: MONSOON_DAY, at: '17:04', kind: 'SOUNDBOX', text: MSG.soundbox(STORY.areaAmount) })

/** The 17:05 instalment line: the lender's grant once the lender decides (x4_lender_request), else the BUILT pause line. */
export function instalmentLine(features: string | undefined = import.meta.env.VITE_FEATURES): Bilingual {
  return isFeatureEnabled('x4_lender_request', features) ? HOLIDAY.granted(STORY.instalment, 'tomorrow') : MSG.instalmentPaused(STORY.instalment)
}

export type Journey = { key: 'rain' | 'illness' | 'questions'; title: string; subtitle: string; now: string; thread: readonly Message[]; soundbox: Message | null }

/** Deck slide 7: the three journeys, in the order the deck tells them. */
export const JOURNEYS: readonly Journey[] = [
  {
    key: 'rain',
    title: 'Rain day',
    subtitle: 'paid automatically',
    now: `${MONSOON_DAY}T17:05:00${IST}`,
    thread: [
      message({ id: 'r1', day: MONSOON_DAY, at: '17:04', kind: 'TEXT', text: MSG.areaPayoutIntro(STORY.nameHi, STORY.nameEn, STORY.drop) }),
      message({ id: 'r2', day: MONSOON_DAY, at: '17:04', kind: 'PAYOUT_CARD', card: areaCard() }),
      message({ id: 'r3', day: MONSOON_DAY, at: '17:05', kind: 'TEXT', text: instalmentLine() }),
    ],
    soundbox: RAIN_SOUNDBOX,
  },
  {
    key: 'illness',
    title: 'Illness',
    subtitle: 'one photo',
    now: `${ILLNESS_DAY}T11:26:00${IST}`,
    thread: [
      message({ id: 'i1', day: ILLNESS_DAY, at: '11:20', kind: 'TEXT', text: MSG.checkinSilent(STORY.nameHi) }),
      message({ id: 'i2', day: ILLNESS_DAY, at: '11:21', kind: 'VOICE', inbound: true, text: ILL, seconds: 6 }),
      message({ id: 'i3', day: ILLNESS_DAY, at: '11:21', kind: 'TEXT', text: MSG.askSlip }),
      message({ id: 'i4', day: ILLNESS_DAY, at: '11:22', kind: 'IMAGE', inbound: true, text: { hi: null, en: 'anil_admission_slip.png' }, media: '/slips/anil_admission_slip.png' }),
      message({ id: 'i5', day: ILLNESS_DAY, at: '11:26', kind: 'PAYOUT_CARD', card: personalCard() }),
    ],
    soundbox: null,
  },
  {
    key: 'questions',
    title: 'Questions',
    subtitle: 'answered with his numbers',
    now: `${MONSOON_DAY}T17:12:00${IST}`,
    thread: [
      message({ id: 'q1', day: MONSOON_DAY, at: '17:12', kind: 'VOICE', inbound: true, text: WHY, seconds: 4 }),
      message({ id: 'q2', day: MONSOON_DAY, at: '17:12', kind: 'TEXT', text: MSG.explainArea('मंगलवार', 'Tuesday', STORY.usualDay, STORY.drop) }),
      message({ id: 'q3', day: MONSOON_DAY, at: '17:13', kind: 'TEXT', inbound: true, text: DISPUTE }),
      message({ id: 'q4', day: MONSOON_DAY, at: '17:13', kind: 'TEXT', text: MSG.disputeAck }),
      message({ id: 'q5', day: MONSOON_DAY, at: '17:13', kind: 'CASE_CHIP', text: MSG.caseChip(STORY.caseId) }),
    ],
    soundbox: null,
  },
]

/**
 * Mock conversation service (SPEC §13.2 intents, §13.5 flows, §13.6 live tests): WHY_AMOUNT →
 * EXPLAIN_AREA, DISPUTE_AMOUNT → DISPUTE case + DISPUTE_ACK + CASE_CHIP, REPORT_ILLNESS → ASK_SLIP,
 * BUY_COVER → COVER_BLOCKED + COVER_LINK, anything else → FALLBACK_HELP. Rule-based, deterministic.
 */
import type { MessageMeta, VoiceDemoKey } from '../api/types'
import { dateEn, MSG, type Bilingual } from './catalogue'
import { openOrFindDispute } from './cases'
import { requestCover } from './endpoints/premium'
import { MERCHANTS, type MockMerchant } from './fixtures'
import { submitSlip } from './personal'
import type { MockRuntime } from './runtime'
import { addDays } from './scenarios'

export type Intent = 'WHY_AMOUNT' | 'DISPUTE_AMOUNT' | 'REPORT_ILLNESS' | 'BUY_COVER' | 'GREETING' | 'UNKNOWN'

const INTENT_RULES: readonly [Intent, RegExp][] = [
  ['WHY_AMOUNT', /क्यों|kyun|kyon|\bwhy\b/i],
  ['DISPUTE_AMOUNT', /ज़्यादा|ज्यादा|नुकसान|zyada|jyada|bigger|\bmore\b/i],
  ['REPORT_ILLNESS', /अस्पताल|बुखार|बीमार|hospital|fever|\bill\b|\bsick\b|bimar/i],
  ['BUY_COVER', /cover|कवर/i],
  ['GREETING', /^(hi|hello|namaste|नमस्ते)\b/i],
]

export function detectIntent(text: string): Intent {
  return INTENT_RULES.find(([, rule]) => rule.test(text))?.[0] ?? 'UNKNOWN'
}

export const VOICE_DEMOS: Readonly<Record<VoiceDemoKey, Bilingual & { hi: string; seconds: number }>> = Object.freeze({
  why: { hi: 'मुझे इतने ही पैसे क्यों मिले?', en: 'Why did I get only this much?', seconds: 4 },
  dispute: { hi: 'मेरा नुकसान ज़्यादा हुआ।', en: 'My loss was bigger.', seconds: 3 },
  ill: { hi: 'मैं अस्पताल में हूँ, बुखार है।', en: "I'm in hospital with a fever.", seconds: 6 },
  cover: { hi: 'कल रेड अलर्ट है। आज ही कवर दे दो।', en: 'Red alert tomorrow. Cover me today.', seconds: 4 },
})

const DEVANAGARI = /[ऀ-ॿ]/

function merchantOrThrow(merchantId: string): MockMerchant {
  const merchant = MERCHANTS[merchantId]
  if (!merchant) throw new Error(`unknown merchant ${merchantId}`)
  return merchant
}

function translate(text: string): Bilingual {
  const known = Object.values(VOICE_DEMOS).find((v) => v.hi === text)
  if (known) return { hi: known.hi, en: known.en }
  return DEVANAGARI.test(text) ? { hi: text, en: '' } : { hi: null, en: text }
}

export function inboundText(rt: MockRuntime, merchantId: string, text: string): void {
  const merchant = merchantOrThrow(merchantId)
  rt.send(merchant.id, { direction: 'INBOUND', kind: 'TEXT', text: translate(text) })
  respond(rt, merchant, text)
}

export function inboundVoiceDemo(rt: MockRuntime, merchantId: string, key: VoiceDemoKey): void {
  const merchant = merchantOrThrow(merchantId)
  const demo = VOICE_DEMOS[key]
  const meta: MessageMeta = { transcript: demo.hi, voice_source: 'browser-simulated', duration_s: demo.seconds }
  rt.send(merchant.id, { direction: 'INBOUND', kind: 'VOICE', text: { hi: demo.hi, en: demo.en }, meta })
  respond(rt, merchant, demo.hi)
}

/** Uploaded recording: the simulated STT hears this scenario's demo utterance (SPEC §0.1). */
export function inboundVoiceUpload(rt: MockRuntime, merchantId: string, mediaUrl: string): void {
  const merchant = merchantOrThrow(merchantId)
  const keyByScenario: Record<string, VoiceDemoKey> = { monsoon: 'why', illness: 'ill', illness_mismatch: 'ill', buy_cover: 'cover' }
  const demo = VOICE_DEMOS[keyByScenario[rt.scenario.name]]
  const meta: MessageMeta = { transcript: demo.hi, voice_source: 'browser-simulated', duration_s: demo.seconds }
  rt.send(merchant.id, { direction: 'INBOUND', kind: 'VOICE', text: { hi: demo.hi, en: demo.en }, mediaUrl, meta })
  respond(rt, merchant, demo.hi)
}

export function inboundPhoto(rt: MockRuntime, merchantId: string, mediaUrl: string, sample: string | null): void {
  const merchant = merchantOrThrow(merchantId)
  const name = sample ?? 'photo.jpg'
  rt.send(merchant.id, { direction: 'INBOUND', kind: 'IMAGE', text: { hi: null, en: name }, mediaUrl })
  const conv = rt.conversation(merchant.id)
  if (!conv.checkinSent || conv.claimId !== null) {
    reply(rt, merchant, MSG.fallbackHelp)
    return
  }
  submitSlip(rt, merchant, mediaUrl, sample)
}

function reply(rt: MockRuntime, merchant: MockMerchant, text: Bilingual): void {
  rt.send(merchant.id, { kind: 'TEXT', text })
}

function respond(rt: MockRuntime, merchant: MockMerchant, text: string): void {
  const intent = detectIntent(text)
  rt.record('ai-agent', 'intent.detected', 'merchant', merchant.id, { intent })
  if (intent === 'WHY_AMOUNT') explainAmount(rt, merchant)
  else if (intent === 'DISPUTE_AMOUNT') dispute(rt, merchant, text)
  else if (intent === 'REPORT_ILLNESS') reportIllness(rt, merchant)
  else if (intent === 'BUY_COVER') quoteCover(rt, merchant)
  else reply(rt, merchant, MSG.fallbackHelp)
}

function latestPaidDecision(rt: MockRuntime, merchantId: string) {
  const creditedDecisionIds = new Set(rt.payouts.filter((p) => p.merchant_id === merchantId && p.status === 'CREDITED').map((p) => p.decision_id))
  return rt.decisions.toReversed().find((d) => creditedDecisionIds.has(d.id)) ?? null
}

function explainAmount(rt: MockRuntime, merchant: MockMerchant): void {
  const decision = latestPaidDecision(rt, merchant.id)
  const ex = decision?.explanation
  if (!ex) {
    reply(rt, merchant, MSG.fallbackHelp)
    return
  }
  if (ex.drop_pct === null) reply(rt, merchant, { hi: ex.formula_hi, en: ex.formula_en })
  else reply(rt, merchant, MSG.explainArea(ex.weekday_hi, ex.weekday_en, ex.expected_day_label, ex.drop_pct))
}

function dispute(rt: MockRuntime, merchant: MockMerchant, text: string): void {
  const { opened, already } = openOrFindDispute(rt, merchant, text, latestPaidDecision(rt, merchant.id))
  reply(rt, merchant, already ? MSG.disputeAlreadyOpen(opened.id) : MSG.disputeAck)
  rt.send(merchant.id, { kind: 'CASE_CHIP', text: MSG.caseChip(opened.id), meta: { case_id: opened.id } })
}

function reportIllness(rt: MockRuntime, merchant: MockMerchant): void {
  const conv = rt.conversation(merchant.id)
  if (!conv.checkinSent) {
    reply(rt, merchant, MSG.fallbackHelp)
    return
  }
  rt.conversations.set(merchant.id, { ...conv, illnessReported: true })
  reply(rt, merchant, MSG.askSlip)
}

/**
 * SPEC §9.5: a new cover always starts after the waiting period; BLOCKED when an alert looms. The quote and the
 * simulated link are the same ones `POST /api/premium/link` makes (`endpoints/premium.ts`), as in the backend.
 */
function quoteCover(rt: MockRuntime, merchant: MockMerchant): void {
  if (merchant.covered) {
    reply(rt, merchant, MSG.fallbackHelp)
    return
  }
  const { quote, premium } = requestCover(rt, merchant)
  if (quote.outcome === 'BLOCKED') reply(rt, merchant, MSG.coverBlocked(quote.starts_on))
  if (premium?.link_url) reply(rt, merchant, MSG.coverLink(quote.first_payment_label, quote.premium_per_day_label, premium.link_url))
}

/** Scenario hook (SPEC §8.3): silent-shop check-in at 11:20 on the illness days. */
export function silentCheckin(rt: MockRuntime): void {
  const merchant = merchantOrThrow(rt.scenario.demoMerchantId)
  rt.conversations.set(merchant.id, { ...rt.conversation(merchant.id), checkinSent: true })
  rt.record('system', 'silence.detected', 'merchant', merchant.id, { silent_dates: [addDays(rt.scenario.day, -1)] })
  rt.addFeed('silence', `${merchant.shop_name} silent all of ${dateEn(addDays(rt.scenario.day, -1))} · WhatsApp check-in sent`, { merchant_id: merchant.id })
  reply(rt, merchant, MSG.checkinSilent(merchant.owner_name_hi))
}

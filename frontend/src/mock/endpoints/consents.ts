/**
 * Mock consent centre (N6 and H23, data-model 5.5, fs-07 section 9; flag n6_consents, 404 `not_found` while it is off):
 * GET /consents, POST /consents/{id}/withdraw, GET /consents/activity and POST /slips/{id}/forget. Like the backend, the
 * prototype seeds three ACTIVE records (source SEEDED, labelled SIMULATED, no audit entry) for the merchant with the
 * seeded cover, and a cover bought through a payment link is agreed `PAYMENT_APP`. A withdrawal replaces the record and
 * never edits a decision, a payout or the audit log. The wording is the notice module's (copy deck 14): the mock copies
 * it, the numbers (`{waiting_days}`, `{paid_through}`) come from the rules and the cover. The activity log is a
 * projection of the audit log through a fixed sentence per action, so it cannot print a patient name.
 */
import type { ConsentPurpose, ActivityItem, ForgetResult, HeldSlip, Consent, WithdrawResult } from '../../miniapp/api/rights'
import { CONSENT_PURPOSES } from '../../miniapp/api/rights'
import { isFeatureEnabled } from '../../features'
import { formatInr } from '../../lib/money'
import { MockHttpError } from '../backend'
import { dateEn, dateHi } from '../catalogue'
import { POLICY_RULES, type MockMerchant } from '../fixtures'
import { merchantParam, notFound, ok, requireOfficer, invalid, type Route, type RouteContext } from '../http'
import type { MockRuntime } from '../runtime'
import { storedCover, SEEDED_COVERS } from './cover'
import { consentId, purchaseGrant, type PurchaseGrant } from './purchaseConsent'

const FLAG = 'n6_consents'
const NOTICE = 'notice-1'
const DEFAULT_LIMIT = 50
const MAX_LIMIT = 200
const SLIP: ConsentPurpose = 'SLIP_DATA_FOR_HOSPITAL_CLAIM'

type Pair = { en: string; hi: string }
type PurposeText = { label: Pair; used: { en: string[]; hi: string[] }; effect: Pair; regrant: Pair }

const TEXT: Readonly<Record<ConsentPurpose, PurposeText>> = {
  SALES_DATA_FOR_CLAIM: {
    label: { en: 'Use my sales data to decide claims and set my premium', hi: 'मेरी बिक्री का डेटा दावे तय करने और प्रीमियम तय करने में इस्तेमाल करें' },
    used: {
      en: ['Daily and hourly sales totals from your Paytm settlement. Soundbox activity, to see whether your shop was open.'],
      hi: ['आपके Paytm सेटलमेंट से रोज़ और घंटे की बिक्री का कुल योग। Soundbox की गतिविधि, यह देखने के लिए कि दुकान खुली थी या नहीं।'],
    },
    effect: {
      en: 'Your cover is cancelled today. Chhatri stops checking your sales, so no new claims are made for you, and your sales are left out of your area\'s index. Claims already decided stay on record. Whether anything is returned, and how much, is set by the cancellation terms (C12). To get cover again you buy again and wait {waiting_days} days.',
      hi: 'आपका कवर आज रद्द हो जाएगा। छतरी आपकी बिक्री देखना बंद कर देगी, इसलिए आपके लिए कोई नया दावा नहीं बनेगा, और आपकी बिक्री आपके इलाके के इंडेक्स से बाहर हो जाएगी। तय हो चुके दावे रिकॉर्ड में रहेंगे। कुछ लौटाया जाए या नहीं, और कितना, यह रद्द करने की शर्तों (C12) से तय होता है। दोबारा कवर के लिए आपको फिर से खरीदना होगा और {waiting_days} दिन रुकना होगा।',
    },
    regrant: { en: 'To turn this on again, buy cover again.', hi: 'इसे दोबारा चालू करने के लिए फिर से कवर खरीदें।' },
  },
  SLIP_DATA_FOR_HOSPITAL_CLAIM: {
    label: { en: 'Read my hospital slip to check a claim', hi: 'दावा जाँचने के लिए मेरी अस्पताल की पर्ची पढ़ें' },
    used: {
      en: ['The photo of the slip you send.', 'Five details read from it: patient name, admission date, discharge date, hospital name, document type.'],
      hi: ['आपकी भेजी पर्ची की फ़ोटो।', 'उससे पढ़ी गई पाँच जानकारियाँ: मरीज़ का नाम, भर्ती की तारीख़, छुट्टी की तारीख़, अस्पताल का नाम, काग़ज़ का प्रकार।'],
    },
    effect: {
      en: 'Chhatri stops reading slips, so no new hospital-cash claim can be made. Your cover and premium stay as they are. Slips already stored stay until you erase them.',
      hi: 'छतरी पर्चियाँ पढ़ना बंद कर देगी, इसलिए अस्पताल-कैश का नया दावा नहीं बन सकेगा। आपका कवर और प्रीमियम जैसे हैं वैसे ही रहेंगे। जमा हो चुकी पर्चियाँ तब तक रहेंगी जब तक आप उन्हें मिटा न दें।',
    },
    regrant: { en: 'To turn this on again, send a slip in the app and agree when asked.', hi: 'इसे दोबारा चालू करने के लिए ऐप में पर्ची भेजें और पूछे जाने पर हामी भरें।' },
  },
  SETTLEMENT_DEDUCTION: {
    label: { en: "Take the next day's premium from my daily settlement", hi: 'मेरे रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटें' },
    used: { en: ["Your day's collections, to check they cover the premium. The premium amount for your zone."], hi: ['आपके दिन की कमाई, यह देखने के लिए कि प्रीमियम निकल सकता है। आपके ज़ोन का प्रीमियम।'] },
    effect: {
      en: 'Chhatri stops taking the premium from your settlement. Your cover keeps working through {paid_through}, the date you have paid for. After that the premium is due, and a claim for a later day is not paid until you pay again with a link.',
      hi: 'छतरी आपके सेटलमेंट से प्रीमियम काटना बंद कर देगी। आपका कवर {paid_through} तक चलता रहेगा, यानी जिस तारीख़ तक आपने भुगतान किया है। उसके बाद प्रीमियम बाकी होगा, और बाद के दिन का दावा तब तक नहीं मिलेगा जब तक आप लिंक से फिर भुगतान नहीं करते।',
    },
    regrant: { en: 'To turn this on again, pay with a new link and agree when asked.', hi: 'इसे दोबारा चालू करने के लिए नए लिंक से भुगतान करें और पूछे जाने पर हामी भरें।' },
  },
}

const CHAT_LINE: Readonly<Record<ConsentPurpose, (m: MockMerchant, paidThrough: string | null) => Pair>> = {
  SALES_DATA_FOR_CLAIM: (m) => ({
    en: `${m.owner_first_en} ji, you turned off the use of your sales data. Your cover is cancelled and no new claims will be made. To get cover again, buy again in the app.`,
    hi: `${m.owner_name_hi} जी, आपने बिक्री के डेटा का इस्तेमाल बंद कर दिया। आपका कवर रद्द हो गया है और कोई नया दावा नहीं बनेगा। दोबारा कवर के लिए ऐप में फिर से खरीदें।`,
  }),
  SLIP_DATA_FOR_HOSPITAL_CLAIM: (m) => ({
    en: `${m.owner_first_en} ji, you turned off slip reading. New slips will not be read. Slips already stored stay until you erase them in the app.`,
    hi: `${m.owner_name_hi} जी, आपने पर्ची पढ़ना बंद कर दिया। नई पर्चियाँ नहीं पढ़ी जाएँगी। जमा पर्चियाँ तब तक रहेंगी जब तक आप ऐप में उन्हें मिटा न दें।`,
  }),
  SETTLEMENT_DEDUCTION: (m, paid) => ({
    en: `${m.owner_first_en} ji, you turned off premium deductions from your settlement. Your cover runs through ${paid ? dateEn(paid) : 'the date you paid for'}. After that, pay again with a link to keep it.`,
    hi: `${m.owner_name_hi} जी, आपने सेटलमेंट से प्रीमियम कटना बंद कर दिया। आपका कवर ${paid ? dateHi(paid) : 'भुगतान की तारीख़'} तक चलेगा। उसके बाद कवर रखने के लिए लिंक से फिर भुगतान करें।`,
  }),
}

type Withdrawal = { purpose: ConsentPurpose; withdrawnAt: string }
type State = { withdrawn: Map<string, Withdrawal[]>; erased: Map<string, string>; slipUploads: Map<string, string> }
const MEMORY = new WeakMap<MockRuntime, State>()
function state(rt: MockRuntime): State {
  const known = MEMORY.get(rt)
  if (known) return known
  const fresh: State = { withdrawn: new Map(), erased: new Map(), slipUploads: new Map() }
  MEMORY.set(rt, fresh)
  return fresh
}

const pad = (n: number): string => String(n).padStart(6, '0')
const withdrawal = (rt: MockRuntime, merchantId: string, purpose: ConsentPurpose): Withdrawal | undefined => state(rt).withdrawn.get(merchantId)?.find((w) => w.purpose === purpose)
const fill = (text: string, params: Record<string, string>): string => text.replace(/\{(\w+)\}/g, (match, name: string) => params[name] ?? match)
const requireFlag = (): void => {
  if (!isFeatureEnabled(FLAG)) throw notFound('route')
}

function openReview(rt: MockRuntime, merchantId: string): boolean {
  return rt.cases.some((c) => c.merchant_id === merchantId && c.kind === 'PERSONAL_CLAIM_REVIEW' && c.status === 'OPEN')
}

/** The stored slips of a merchant: one per personal-claim review case (the evidence the officer reads). */
export function heldSlips(rt: MockRuntime, merchantId: string): HeldSlip[] {
  const cases = rt.cases.filter((c) => c.merchant_id === merchantId && c.kind === 'PERSONAL_CLAIM_REVIEW' && c.decision !== null)
  return cases.map((c, index): HeldSlip => {
    const slipId = `MD-${pad(index + 2)}`
    const erasedAt = state(rt).erased.get(slipId) ?? null
    const blocked = c.status === 'OPEN'
    return {
      slip_id: slipId,
      claim_id: c.decision?.claim_id ?? 'CL-000000',
      received_at: c.opened_at,
      state: erasedAt ? 'ERASED' : 'HELD',
      erased_at: erasedAt,
      can_erase: !blocked && erasedAt === null,
      blocked_reason: blocked && erasedAt === null ? 'case_open' : null,
    }
  })
}

function consentView(rt: MockRuntime, merchant: MockMerchant, purpose: ConsentPurpose): Consent {
  const cover = storedCover(rt, merchant.id)
  const text = TEXT[purpose]
  const params = { waiting_days: String(POLICY_RULES.cover.waiting_period_days), paid_through_en: '', paid_through: '' }
  const paid = cover?.prepaid_through ?? null
  const gone = withdrawal(rt, merchant.id, purpose)
  const seeded = cover !== null && SEEDED_COVERS[merchant.id] !== undefined && cover.id === SEEDED_COVERS[merchant.id].id
  const grant: PurchaseGrant | null = seeded ? null : purchaseGrant(rt, merchant.id)
  const given = cover !== null && (grant === null || grant.purposes.includes(purpose))
  const status = !given ? 'NOT_GIVEN' : gone ? 'WITHDRAWN' : 'ACTIVE'
  const sales = purpose === 'SALES_DATA_FOR_CLAIM'
  const blocked = sales && openReview(rt, merchant.id)
  const effect = (lang: 'en' | 'hi'): string => fill(text.effect[lang], { ...params, paid_through: paid ? (lang === 'en' ? dateEn(paid) : dateHi(paid)) : lang === 'en' ? 'the date you paid for' : 'भुगतान की तारीख़' })
  const uploaded = purpose === SLIP ? state(rt).slipUploads.get(merchant.id) : undefined
  if (uploaded !== undefined && (gone === undefined || uploaded >= gone.withdrawnAt)) return slipUploadView(merchant, uploaded, effect)
  return {
    consent_id: given ? consentId(merchant.id, purpose) : null,
    purpose,
    purpose_label_en: text.label.en,
    purpose_label_hi: text.label.hi,
    status,
    granted_at: given ? (grant?.at ?? cover?.purchased_at ?? null) : null,
    withdrawn_at: gone?.withdrawnAt ?? null,
    source: !given ? null : seeded ? 'SEEDED' : (grant?.source ?? 'PAYMENT_APP'),
    notice_version: !given || seeded ? null : grant ? grant.notice_version : NOTICE,
    current_notice_version: NOTICE,
    required_to_buy: purpose !== SLIP,
    data_used_en: text.used.en,
    data_used_hi: text.used.hi,
    withdraw_effect_en: effect('en'),
    withdraw_effect_hi: effect('hi'),
    can_withdraw: status === 'ACTIVE' && !blocked,
    blocked_reason: status === 'ACTIVE' && blocked ? 'case_open' : null,
    regrant_en: text.regrant.en,
    regrant_hi: text.regrant.hi,
    held: purpose === SLIP ? heldSlips(rt, merchant.id) : null,
  }
}

/** The slip consent given with a photo (SLIP_UPLOAD): ACTIVE from that time, under the notice in force. */
function slipUploadView(merchant: MockMerchant, at: string, effect: (lang: 'en' | 'hi') => string): Consent {
  const text = TEXT[SLIP]
  return {
    consent_id: consentId(merchant.id, SLIP),
    purpose: SLIP,
    purpose_label_en: text.label.en,
    purpose_label_hi: text.label.hi,
    status: 'ACTIVE',
    granted_at: at,
    withdrawn_at: null,
    source: 'SLIP_UPLOAD',
    notice_version: NOTICE,
    current_notice_version: NOTICE,
    required_to_buy: false,
    data_used_en: text.used.en,
    data_used_hi: text.used.hi,
    withdraw_effect_en: effect('en'),
    withdraw_effect_hi: effect('hi'),
    can_withdraw: true,
    blocked_reason: null,
    regrant_en: text.regrant.en,
    regrant_hi: text.regrant.hi,
    held: null,
  }
}

/**
 * The slip gate of the pre-check (backend consent/slip_gate.py): with n6_consents off it passes; with it on, a merchant
 * with no ACTIVE slip consent gives it in the same call (`consent: true` and the notice in force), which is recorded
 * as SLIP_UPLOAD; otherwise 409 `consent_required` and nothing is read.
 */
export function requireSlipConsent(rt: MockRuntime, merchant: MockMerchant, consent: unknown, noticeVersion: unknown): void {
  if (!isFeatureEnabled(FLAG) || consentView(rt, merchant, SLIP).status === 'ACTIVE') return
  if (consent !== true || noticeVersion !== NOTICE) throw new MockHttpError('consent_required', 'we need your OK before we read a slip', 409)
  const at = rt.nowIso
  state(rt).slipUploads.set(merchant.id, at)
  rt.record(`merchant:${merchant.id}`, 'consent.granted', 'consent', consentId(merchant.id, SLIP), { merchant_id: merchant.id, purpose: SLIP, source: 'SLIP_UPLOAD', notice_version: NOTICE, payment_id: null })
}

function listConsents(ctx: RouteContext) {
  requireFlag()
  const merchant = merchantParam(ctx)
  const all = CONSENT_PURPOSES.map((purpose) => consentView(ctx.backend.runtime, merchant, purpose))
  return ok(all, { total: all.length, limit: all.length, offset: 0 })
}

function withdraw(ctx: RouteContext) {
  requireFlag()
  requireOfficer(ctx)
  const rt = ctx.backend.runtime
  const merchant = merchantParam(ctx)
  const found = CONSENT_PURPOSES.map((purpose) => consentView(rt, merchant, purpose)).find((c) => c.consent_id === ctx.params[1])
  if (!found) throw notFound(`consent ${ctx.params[1]}`)
  if (found.status === 'WITHDRAWN') throw new MockHttpError('already_withdrawn', 'this consent is already withdrawn', 409)
  if (found.status !== 'ACTIVE') throw notFound(`consent ${ctx.params[1]}`)
  if (!found.can_withdraw) throw new MockHttpError('case_open', 'a claim review is open', 409)
  const at = rt.nowIso
  state(rt).withdrawn.set(merchant.id, [...(state(rt).withdrawn.get(merchant.id) ?? []), { purpose: found.purpose, withdrawnAt: at }])
  rt.record(`merchant:${merchant.id}`, 'consent.withdrawn', 'consent', found.consent_id ?? '', { merchant_id: merchant.id, purpose: found.purpose, via: 'demo_officer_session' })
  if (found.purpose === 'SALES_DATA_FOR_CLAIM') rt.record(`merchant:${merchant.id}`, 'cover.cancelled', 'cover', storedCover(rt, merchant.id)?.id ?? '', { merchant_id: merchant.id, reason: 'SALES_CONSENT_WITHDRAWN' })
  const line = CHAT_LINE[found.purpose](merchant, storedCover(rt, merchant.id)?.prepaid_through ?? null)
  rt.send(merchant.id, { kind: 'TEXT', text: line })
  const result: WithdrawResult = {
    consent_id: found.consent_id ?? '',
    purpose: found.purpose,
    status: 'WITHDRAWN',
    withdrawn_at: at,
    action_taken_en: found.withdraw_effect_en,
    action_taken_hi: found.withdraw_effect_hi,
    cover_status: found.purpose === 'SALES_DATA_FOR_CLAIM' ? 'CANCELLED' : 'ACTIVE',
  }
  return ok(result)
}

type Sentence = { purpose: ConsentPurpose; kind: ActivityItem['kind']; en: string; hi: string; ref: ActivityItem['ref'] }

function sentenceOf(rt: MockRuntime, entry: MockRuntime['audit'][number], merchantId: string): Sentence | null {
  const data = entry.data as Record<string, unknown>
  const day = entry.at.slice(0, 10)
  if (entry.action === 'silence.detected' && entry.subject_id === merchantId) {
    return { purpose: 'SALES_DATA_FOR_CLAIM', kind: 'USED', en: `Your shop's sales were checked for ${dateEn(day)}. No sales were found.`, hi: `${dateHi(day)} के लिए आपकी दुकान की बिक्री देखी गई। कोई बिक्री नहीं मिली।`, ref: null }
  }
  if (entry.action === 'decision.made' && entry.subject_type === 'decision') {
    const decision = rt.decisions.find((d) => d.id === entry.subject_id && d.merchant_id === merchantId)
    if (!decision) return null
    const ref = { type: 'decision', id: decision.id }
    const personal = decision.checks.some((c) => c.code === 'NAME_MATCHES_KYC')
    if (!personal) return { purpose: 'SALES_DATA_FOR_CLAIM', kind: 'USED', en: `Your sales for ${dateEn(day)} were compared with your usual day. Decision ${decision.id}.`, hi: `${dateHi(day)} की आपकी बिक्री की तुलना आपके आम दिन से की गई। फ़ैसला ${decision.id}।`, ref }
    return { purpose: SLIP, kind: 'USED', en: `Your slip details were checked for a claim. Decision ${decision.id}.`, hi: `आपके दावे के लिए पर्ची की जानकारी जाँची गई। फ़ैसला ${decision.id}।`, ref }
  }
  if (data.merchant_id !== merchantId) return null
  if (entry.action === 'consent.withdrawn') {
    const purpose = data.purpose as ConsentPurpose
    return { purpose, kind: 'WITHDRAWN', en: `You turned off: ${TEXT[purpose].label.en}.`, hi: `आपने बंद किया: ${TEXT[purpose].label.hi}।`, ref: { type: 'consent', id: entry.subject_id } }
  }
  if (entry.action === 'cover.cancelled') return { purpose: 'SALES_DATA_FOR_CLAIM', kind: 'EFFECT', en: 'Your cover was cancelled because sales data was turned off.', hi: 'बिक्री का डेटा बंद करने के कारण आपका कवर रद्द हुआ।', ref: null }
  if (entry.action === 'slip.erased') return { purpose: SLIP, kind: 'ERASED', en: 'Your slip data was erased.', hi: 'आपकी पर्ची का डेटा मिटा दिया गया।', ref: { type: 'media', id: entry.subject_id } }
  if (entry.action === 'premium.settled' && typeof data.amount_paise === 'number') {
    return { purpose: 'SETTLEMENT_DEDUCTION', kind: 'USED', en: `Tomorrow's premium of ${formatInr(data.amount_paise)} was taken from today's collections.`, hi: `आज की कमाई से कल का ${formatInr(data.amount_paise)} का प्रीमियम लिया गया।`, ref: null }
  }
  return null
}

function whole(ctx: RouteContext, name: string, fallback: number, min: number, max: number): number {
  const raw = ctx.query.get(name)
  if (raw === null) return fallback
  const value = Number(raw)
  if (!Number.isInteger(value) || value < min || value > max) throw invalid(name, `${min} to ${max}`)
  return value
}

function activity(ctx: RouteContext) {
  requireFlag()
  const rt = ctx.backend.runtime
  const merchant = merchantParam(ctx)
  const limit = whole(ctx, 'limit', DEFAULT_LIMIT, 1, MAX_LIMIT)
  const offset = whole(ctx, 'offset', 0, 0, Number.MAX_SAFE_INTEGER)
  const purpose = ctx.query.get('purpose')
  if (purpose !== null && !(CONSENT_PURPOSES as readonly string[]).includes(purpose)) throw invalid('purpose', CONSENT_PURPOSES.join(', '))
  const rows = rt.audit
    .map((entry): ActivityItem | null => {
      const sentence = sentenceOf(rt, entry, merchant.id)
      return sentence && { seq: entry.seq, at: entry.at, purpose: sentence.purpose, kind: sentence.kind, text_en: sentence.en, text_hi: sentence.hi, ref: sentence.ref }
    })
    .filter((item): item is ActivityItem => item !== null && (purpose === null || item.purpose === purpose))
    .toReversed()
  return ok(rows.slice(offset, offset + limit), { total: rows.length, limit, offset })
}

function forget(ctx: RouteContext) {
  requireFlag()
  requireOfficer(ctx)
  const rt = ctx.backend.runtime
  const merchant = merchantParam(ctx)
  const slip = heldSlips(rt, merchant.id).find((s) => s.slip_id === ctx.params[1])
  if (!slip) throw notFound(`slip ${ctx.params[1]}`)
  if (slip.state === 'ERASED') throw new MockHttpError('already_erased', 'this slip was erased before', 409)
  if (!slip.can_erase) throw new MockHttpError('case_open', 'a claim review is open', 409)
  const at = rt.nowIso
  state(rt).erased.set(slip.slip_id, at)
  const decisions = rt.decisions.filter((d) => d.claim_id === slip.claim_id)
  rt.record(`merchant:${merchant.id}`, 'slip.erased', 'media', slip.slip_id, { merchant_id: merchant.id, claim_id: slip.claim_id, decisions: decisions.map((d) => d.id), via: 'demo_officer_session' })
  const result: ForgetResult = {
    slip_id: slip.slip_id,
    claim_id: slip.claim_id,
    erased_at: at,
    erased: { photo: true, claim_fields: true, decisions: decisions.length, case_fields: rt.cases.filter((c) => c.decision?.claim_id === slip.claim_id).length, messages: rt.messages.filter((m) => m.merchant_id === merchant.id && m.media_url !== null).length },
    kept: ['DECISION_OUTCOME', 'AMOUNT', 'CHECK_CODES_AND_RESULTS', 'AUDIT_ENTRIES'],
    audit_note_en: 'The activity log cannot be edited, so it can still show the name and dates from this slip in entries written before today.',
    audit_note_hi: 'गतिविधि का लॉग बदला नहीं जा सकता, इसलिए आज से पहले लिखी गई प्रविष्टियों में इस पर्ची का नाम और तारीख़ें दिख सकती हैं।',
  }
  return ok(result)
}

export const CONSENT_ROUTES: readonly Route[] = [
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/consents$/, handler: listConsents },
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/consents\/activity$/, handler: activity },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/consents\/(CN-\d{6,})\/withdraw$/, handler: withdraw },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/slips\/(MD-\d{6,})\/forget$/, handler: forget },
]

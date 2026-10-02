/**
 * Mock POST /api/premium/link and POST /api/webhooks/paytm (SPEC §9.5, §9.7, §14.3; the buy flow of DEMO.md). The
 * quote follows `policy/cover.py`: a cover bought while an alert for the zone is valid, or about to start within the
 * look-ahead, is BLOCKED (the merchant is told it starts after the waiting period, and still gets a link for later);
 * otherwise OK. The link is the simulated Paytm link of `integrations/paytm_sim.py`: its code is a hash of the
 * merchant, the amount, the purpose and the link's sequence number, so Ramesh's first link is `sim-7BFFBE` here and in
 * the backend. The paid callback follows `ledger/premiums.py`: it makes a cover that starts after the waiting period,
 * or extends the prepaid date of an existing one contiguously, then tells the merchant. With `n6_consents` on, the link
 * also checks the consent block and the paid callback records the consents (`purchaseConsent.ts`).
 */
import type { Alert, CoverQuote, PaytmAck, PremiumLinkResult, PremiumPayment } from '../../api/types'
import { formatInr } from '../../lib/money'
import { dateEn, dateHi } from '../catalogue'
import { POLICY_RULES, zonePremiumPaise, type MockMerchant } from '../fixtures'
import { bodyField, invalid, merchantById, MockHttpError, notFound, ok, requireOfficer, type Route, type RouteContext, type RouteResult } from '../http'
import type { MockRuntime } from '../runtime'
import { addDays } from '../scenarios'
import { sha256Hex } from '../sha256'
import { deriveCover, storedCover, type StoredCover } from './cover'
import { checkPurchase, expectGrant, grantOnPayment } from './purchaseConsent'

const SIM_URL_PREFIX = 'https://paytm.me/sim-'
const CODE_LENGTH = 6
const PAISE_PER_RUPEE = 100
const MS_PER_HOUR = 3_600_000
const MS_PER_DAY = 86_400_000
const MERCHANT_ID = /^S-\d{4}$/
const PAID_STATUSES: readonly string[] = ['TXN_SUCCESS', 'SUCCESS', 'PAID']

const BLOCKED_REASON = { en: 'New cover starts after the waiting period', hi: 'नया कवर वेटिंग पीरियड के बाद शुरू होता है' }
const okReason = (days: number) => ({
  en: `No alert for your area. New cover starts after the ${days}-day waiting period`,
  hi: `आपके इलाके के लिए कोई अलर्ट नहीं है। नया कवर ${days} दिन के वेटिंग पीरियड के बाद शुरू होता है`,
})

/** Paytm's rupee string with two decimals, from integer paise (no floating point). */
function rupeeString(amountPaise: number): string {
  return `${Math.trunc(amountPaise / PAISE_PER_RUPEE)}.${String(amountPaise % PAISE_PER_RUPEE).padStart(2, '0')}`
}

/** The six-character code of a simulated link (paytm_sim.py): sha256 of "merchant|amount|purpose|sequence". */
export function simulatedLinkCode(merchantId: string, amountPaise: number, purpose: string, sequence: number): string {
  return sha256Hex(`${merchantId}|${rupeeString(amountPaise)}|${purpose}|${sequence}`).slice(0, CODE_LENGTH).toUpperCase()
}

/** `policy/cover.py is_relevant_alert`: issued, not over, and valid now or starting within the look-ahead. */
function blockingAlert(rt: MockRuntime, zoneId: string): Alert | null {
  const now = Date.parse(rt.nowIso)
  const lookahead = POLICY_RULES.cover.alert_lookahead_hours * MS_PER_HOUR
  const relevant = rt.scenario.alerts.filter((a) => {
    if (!a.zone_ids.includes(zoneId) || Date.parse(a.issued_at) > now || Date.parse(a.valid_to) <= now) return false
    return Date.parse(a.valid_from) <= now || Date.parse(a.valid_from) < now + lookahead
  })
  return relevant.toSorted((a, b) => Date.parse(a.valid_from) - Date.parse(b.valid_from) || a.id.localeCompare(b.id))[0] ?? null
}

function makeQuote(rt: MockRuntime, merchant: MockMerchant): CoverQuote {
  const waiting = POLICY_RULES.cover.waiting_period_days
  const days = POLICY_RULES.premium.first_payment_days
  const perDay = zonePremiumPaise(merchant.zone_id)
  const alert = blockingAlert(rt, merchant.zone_id)
  const reason = alert ? BLOCKED_REASON : okReason(waiting)
  return {
    id: rt.nextId('Q'),
    merchant_id: merchant.id,
    outcome: alert ? 'BLOCKED' : 'OK',
    requested_at: rt.nowIso,
    starts_on: addDays(rt.nowIso.slice(0, 10), waiting),
    premium_per_day_paise: perDay,
    premium_per_day_label: formatInr(perDay),
    first_payment_paise: perDay * days,
    first_payment_label: formatInr(perDay * days),
    days_prepaid: days,
    reason_en: reason.en,
    reason_hi: reason.hi,
    blocking_alert_id: alert?.id ?? null,
  }
}

function makeLink(rt: MockRuntime, merchant: MockMerchant, quote: CoverQuote): PremiumPayment {
  const purpose = `Chhatri cover premium, ${quote.days_prepaid} days from ${quote.starts_on}`
  const taken = new Set(rt.premiums.map((p) => p.link_id))
  let sequence = rt.premiums.length
  let code = ''
  do {
    sequence += 1
    code = simulatedLinkCode(merchant.id, quote.first_payment_paise, purpose, sequence)
  } while (taken.has(`sim-${code}`))
  return {
    id: rt.nextId('PR'),
    merchant_id: merchant.id,
    amount_paise: quote.first_payment_paise,
    amount_label: formatInr(quote.first_payment_paise),
    method: 'PAYMENT_LINK',
    covers_from: quote.starts_on,
    covers_to: addDays(quote.starts_on, quote.days_prepaid - 1),
    status: 'PENDING',
    link_id: `sim-${code}`,
    link_url: `${SIM_URL_PREFIX}${code}`,
    source: 'simulated',
    created_at: rt.nowIso,
    paid_at: null,
  }
}

/** "25 August" to "25 Aug", the short form of the backend's feed lines. */
function dayMonth(iso: string): string {
  const [day, month] = dateEn(iso).split(' ')
  return `${day} ${month.slice(0, 3)}`
}

/** Quote cover and make the simulated link, for the API route and for the chat (BUY_COVER). The quote is always stored and audited. */
export function requestCover(rt: MockRuntime, merchant: MockMerchant): PremiumLinkResult {
  const quote = makeQuote(rt, merchant)
  rt.quotes = [...rt.quotes, quote]
  rt.record('policy-engine', 'cover.quoted', 'quote', quote.id, {
    merchant_id: merchant.id,
    outcome: quote.outcome,
    starts_on: quote.starts_on,
    premium_per_day_paise: quote.premium_per_day_paise,
    first_payment_paise: quote.first_payment_paise,
    blocking_alert_id: quote.blocking_alert_id,
  })
  const premium = makeLink(rt, merchant, quote)
  rt.premiums = [...rt.premiums, premium]
  rt.record('system', 'premium.link_created', 'premium', premium.id, { quote_id: quote.id, link_id: premium.link_id })
  rt.addFeed('cover', `${merchant.shop_name} asked for cover: ${quote.outcome}, starts ${dayMonth(quote.starts_on)}`, { merchant_id: merchant.id })
  return { quote, premium }
}

const daysInclusive = (from: string, to: string): number => Math.round((Date.parse(to) - Date.parse(from)) / MS_PER_DAY) + 1

/** `ledger/premiums.py mark_paid`: a new cover starts at `covers_from`; an existing one is extended contiguously. */
function coverAfterPayment(rt: MockRuntime, link: PremiumPayment): { first: string; last: string; cover: StoredCover } {
  const days = daysInclusive(link.covers_from, link.covers_to)
  const existing = storedCover(rt, link.merchant_id)
  const first = existing === null ? link.covers_from : existing.prepaid_through === null ? existing.starts_on : addDays(existing.prepaid_through, 1)
  const last = addDays(first, days - 1)
  const cover: StoredCover = existing
    ? { ...existing, prepaid_through: last }
    : {
        id: `CV-${link.merchant_id}-${link.covers_from.replaceAll('-', '')}`,
        merchant_id: link.merchant_id,
        purchased_at: rt.nowIso,
        starts_on: link.covers_from,
        premium_per_day_paise: link.amount_paise / days,
        prepaid_through: last,
      }
  return { first, last, cover }
}

/** PREMIUM_PAID_STARTS or PREMIUM_PAID_ACTIVE of the backend catalogue, told on WhatsApp after the paid callback. */
function tellPremiumPaid(rt: MockRuntime, merchant: MockMerchant, paid: PremiumPayment, cover: StoredCover): void {
  const amount = formatInr(paid.amount_paise)
  const intro = { hi: `${merchant.owner_name_hi} जी, आपका ${amount} का प्रीमियम मिल गया।`, en: `${merchant.owner_first_en} ji, we received your ${amount} premium.` }
  const starts = cover.starts_on > rt.nowIso.slice(0, 10)
  rt.send(merchant.id, {
    kind: 'TEXT',
    text: starts
      ? {
          hi: `${intro.hi} आपका कवर ${dateHi(cover.starts_on)} से शुरू होगा और ${dateHi(paid.covers_to)} तक का प्रीमियम जमा है।`,
          en: `${intro.en} Your cover starts on ${dateEn(cover.starts_on)} and is paid through ${dateEn(paid.covers_to)}.`,
        }
      : {
          hi: `${intro.hi} आपका कवर चालू है और ${dateHi(paid.covers_to)} तक का प्रीमियम जमा है।`,
          en: `${intro.en} Your cover is active and paid through ${dateEn(paid.covers_to)}.`,
        },
  })
}

function markPaid(rt: MockRuntime, link: PremiumPayment, txnId: string | null): void {
  const merchant = merchantById(link.merchant_id)
  const { first, last, cover } = coverAfterPayment(rt, link)
  const paid: PremiumPayment = { ...link, status: 'PAID', paid_at: rt.nowIso, covers_from: first, covers_to: last }
  rt.covers.set(merchant.id, cover)
  rt.premiums = rt.premiums.map((p) => (p.id === paid.id ? paid : p))
  rt.record('system', 'premium.paid', 'premium', paid.id, { txn_id: txnId, cover_status: deriveCover(cover, rt.nowIso.slice(0, 10)).status })
  rt.addFeed('premium', `${merchant.shop_name} paid ${paid.amount_label} premium · covered ${dayMonth(first)}–${dayMonth(last)}`, { merchant_id: merchant.id })
  grantOnPayment(rt, paid)
  tellPremiumPaid(rt, merchant, paid, cover)
}

function postLink(ctx: RouteContext): RouteResult {
  requireOfficer(ctx)
  const id = bodyField(ctx.body, 'merchant_id')
  if (typeof id !== 'string' || !MERCHANT_ID.test(id)) throw invalid('merchant_id', 'must look like S-0142')
  const rt = ctx.backend.runtime
  const merchant = merchantById(id)
  const noticeVersion = bodyField(ctx.body, 'notice_version')
  const purposes = checkPurchase(rt, merchant.id, bodyField(ctx.body, 'consents'), noticeVersion)
  const result = requestCover(rt, merchant)
  if (result.premium) expectGrant(rt, result.premium, purposes, noticeVersion)
  return ok(result)
}

/** The first of the spellings Paytm uses (`paytm_callback.py`), or null. */
function callbackField(body: unknown, names: readonly string[]): string | null {
  for (const name of names) {
    const value = bodyField(body, name)
    if (typeof value === 'string' && value.trim() !== '') return value.trim()
  }
  return null
}

function paytmCallback(ctx: RouteContext): RouteResult {
  const linkId = callbackField(ctx.body, ['linkId', 'LINKID', 'link_id'])
  const status = callbackField(ctx.body, ['STATUS', 'status'])
  if (linkId === null || status === null) {
    const missing = { ...(linkId === null ? { linkId: 'required' } : {}), ...(status === null ? { STATUS: 'required' } : {}) }
    throw new MockHttpError('validation_error', 'invalid request', 422, missing)
  }
  if (!PAID_STATUSES.includes(status.toUpperCase())) return ok({ status: 'ignored', link_id: linkId } satisfies PaytmAck)
  const rt = ctx.backend.runtime
  const txnId = callbackField(ctx.body, ['TXNID', 'txnId', 'txn_id'])
  if (txnId !== null && rt.paidTransactions.has(txnId)) return ok({ status: 'duplicate', link_id: linkId } satisfies PaytmAck)
  const link = rt.premiums.find((p) => p.link_id === linkId)
  if (!link) throw notFound(`payment link ${linkId}`)
  if (txnId !== null) rt.paidTransactions.add(txnId)
  if (link.status === 'PENDING') markPaid(rt, link, txnId)
  return ok({ status: 'paid', link_id: linkId } satisfies PaytmAck)
}

export const PREMIUM_ROUTES: readonly Route[] = [
  { method: 'POST', pattern: /^\/api\/premium\/link$/, handler: postLink },
  { method: 'POST', pattern: /^\/api\/webhooks\/paytm$/, handler: paytmCallback },
]

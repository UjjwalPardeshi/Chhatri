/**
 * The consent block of a cover purchase in the mock (N6, fs-07 sections 9.3 and 9.5), after backend
 * `consent/purchase.py` and `consent/ledger.py`. With `n6_consents` off none of this runs. With it on, a merchant with
 * no live cover must send the two purposes needed to buy and the notice in force (422 otherwise, nothing stored); the
 * ticks are remembered against the payment link and become consent only when that link is paid: `PAYMENT_APP` at the
 * time of the link request. A link the merchant asked for in the chat carries no ticks, so it grants sales and
 * settlement as `PAYMENT_CHAT`.
 */
import type { PremiumPayment } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import type { ConsentPurpose } from '../../miniapp/api/rights'
import { MERCHANTS } from '../fixtures'
import { MockHttpError } from '../http'
import type { MockRuntime } from '../runtime'
import { deriveCover, storedCover } from './cover'

export const CONSENT_FLAG = 'n6_consents'
export const NOTICE_VERSION = 'notice-1'
const REQUIRED_TO_BUY: readonly ConsentPurpose[] = ['SALES_DATA_FOR_CLAIM', 'SETTLEMENT_DEDUCTION']
const CHAT_PURPOSES: readonly ConsentPurpose[] = REQUIRED_TO_BUY
const KNOWN: readonly string[] = ['SALES_DATA_FOR_CLAIM', 'SLIP_DATA_FOR_HOSPITAL_CLAIM', 'SETTLEMENT_DEDUCTION']

const pad = (n: number): string => String(n).padStart(6, '0')

/** The id of a merchant's consent record for one purpose: `CN-` and a number fixed by the merchant and the purpose. */
export function consentId(merchantId: string, purpose: ConsentPurpose): string {
  return `CN-${pad(Object.keys(MERCHANTS).indexOf(merchantId) * KNOWN.length + KNOWN.indexOf(purpose) + 1)}`
}

/** What a paid link granted: the purposes, how, when and under which notice. */
export type PurchaseGrant = { purposes: readonly ConsentPurpose[]; source: 'PAYMENT_APP' | 'PAYMENT_CHAT'; at: string; notice_version: string | null }

type Pending = { purposes: readonly ConsentPurpose[]; notice_version: string; at: string }
type Ledger = { pending: Map<string, Pending>; granted: Map<string, PurchaseGrant> }

const LEDGERS = new WeakMap<MockRuntime, Ledger>()

function ledger(rt: MockRuntime): Ledger {
  const known = LEDGERS.get(rt)
  if (known) return known
  const fresh: Ledger = { pending: new Map(), granted: new Map() }
  LEDGERS.set(rt, fresh)
  return fresh
}

/** The `consents` of the request body: known purposes only, each once; anything else is a 422 like the backend's schema. */
function purposesOf(raw: unknown): ConsentPurpose[] {
  if (raw === undefined || raw === null) return []
  if (!Array.isArray(raw) || raw.length > KNOWN.length || raw.some((p) => typeof p !== 'string' || !KNOWN.includes(p))) {
    throw new MockHttpError('validation_error', 'invalid request', 422, { consents: 'unknown purpose' })
  }
  return [...new Set(raw as ConsentPurpose[])]
}

const hasLiveCover = (rt: MockRuntime, merchantId: string): boolean => {
  const status = deriveCover(storedCover(rt, merchantId), rt.nowIso.slice(0, 10)).status
  return status === 'ACTIVE' || status === 'WAITING'
}

/** `check_purchase`: raises the 422 of an incomplete or stale block; a no-op with the flag off or for a renewal. */
export function checkPurchase(rt: MockRuntime, merchantId: string, consents: unknown, noticeVersion: unknown): ConsentPurpose[] {
  if (!isFeatureEnabled(CONSENT_FLAG)) return []
  const purposes = purposesOf(consents)
  if (hasLiveCover(rt, merchantId)) return purposes
  const fields: Record<string, string> = {}
  if (!REQUIRED_TO_BUY.every((p) => purposes.includes(p))) fields.consents = 'required purposes missing'
  if (noticeVersion !== NOTICE_VERSION) fields.notice_version = 'out of date'
  if (Object.keys(fields).length > 0) throw new MockHttpError('validation_error', 'consent is incomplete', 422, fields)
  return purposes
}

/** `expect_grant`: remember the ticks against the link; they are recorded when it is paid. */
export function expectGrant(rt: MockRuntime, premium: PremiumPayment, purposes: readonly ConsentPurpose[], noticeVersion: unknown): void {
  if (!isFeatureEnabled(CONSENT_FLAG) || purposes.length === 0) return
  ledger(rt).pending.set(premium.id, { purposes, notice_version: typeof noticeVersion === 'string' ? noticeVersion : '', at: rt.nowIso })
}

/** `reconcile` for one paid link: grant each purpose once per merchant and write `consent.granted`. */
export function grantOnPayment(rt: MockRuntime, paid: PremiumPayment): void {
  if (!isFeatureEnabled(CONSENT_FLAG)) return
  const book = ledger(rt)
  if (book.granted.has(paid.merchant_id)) return
  const pending = book.pending.get(paid.id)
  const grant: PurchaseGrant = pending
    ? { purposes: pending.purposes, source: 'PAYMENT_APP', at: pending.at, notice_version: pending.notice_version }
    : { purposes: CHAT_PURPOSES, source: 'PAYMENT_CHAT', at: paid.created_at, notice_version: null }
  book.granted.set(paid.merchant_id, grant)
  for (const purpose of grant.purposes) {
    rt.record(`merchant:${paid.merchant_id}`, 'consent.granted', 'consent', consentId(paid.merchant_id, purpose), {
      merchant_id: paid.merchant_id,
      purpose,
      source: grant.source,
      notice_version: grant.notice_version,
      payment_id: paid.id,
    })
  }
}

/** What the merchant's paid link granted, or null (no purchase in this load, or the flag off). */
export function purchaseGrant(rt: MockRuntime, merchantId: string): PurchaseGrant | null {
  return ledger(rt).granted.get(merchantId) ?? null
}

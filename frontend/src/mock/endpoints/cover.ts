/**
 * Mock GET /api/merchants/{id}/cover (data-model 5.1, fs-07 section 5.3). The status is derived from `starts_on` and
 * the replay clock, never stored and never read from the device clock: a cover whose start date has come is ACTIVE,
 * one that has not is WAITING, and a merchant with no cover record is NONE (an API-only value, with nulls for the
 * dates and amounts). The price is the zone's price from the copied premiums.json. The two status sentences are the
 * backend catalogue's COVER_STATUS_ACTIVE, _STARTS and _UNPAID, and the proposed COVER_STATUS_NONE (fs-07).
 */
import type { Cover, CoverStatus } from '../../api/types'
import { formatInr } from '../../lib/money'
import { dateEn, dateHi } from '../catalogue'
import { POLICY_RULES, zonePremiumPaise, type MockMerchant } from '../fixtures'
import { merchantParam, ok, type Route } from '../http'
import type { MockRuntime } from '../runtime'
import { alertFor, alertValidAt } from '../zones'

/** A cover record: the pilot cover seeded for Anil, or one made by a paid premium link. */
export type StoredCover = {
  id: string
  merchant_id: string
  purchased_at: string
  starts_on: string
  premium_per_day_paise: number
  prepaid_through: string | null
}

export type MockCoverStatus = Extract<CoverStatus, 'NONE' | 'WAITING' | 'ACTIVE'>

const PAISE_PER_RUPEE = 100

/** Anil's pilot cover as the backend seeds it (`sim/city.py`: bought 10 Mar 2025, 7 days' wait, prepaid to 22 Aug). */
export const SEEDED_COVERS: Readonly<Record<string, StoredCover>> = Object.freeze({
  'S-0142': Object.freeze({
    id: 'CV-0142',
    merchant_id: 'S-0142',
    purchased_at: '2025-03-10T11:00:00+05:30',
    starts_on: '2025-03-17',
    premium_per_day_paise: zonePremiumPaise('Z7'),
    prepaid_through: '2025-08-22',
  }),
})

export function storedCover(rt: MockRuntime, merchantId: string): StoredCover | null {
  return rt.covers.get(merchantId) ?? SEEDED_COVERS[merchantId] ?? null
}

/** fs-07 5.3: WAITING before `starts_on`; premium due when the prepaid days are over (or were never paid). */
export function deriveCover(cover: StoredCover | null, today: string): { status: MockCoverStatus; premium_due: boolean } {
  if (cover === null) return { status: 'NONE', premium_due: false }
  if (today < cover.starts_on) return { status: 'WAITING', premium_due: false }
  return { status: 'ACTIVE', premium_due: cover.prepaid_through === null || cover.prepaid_through < today }
}

type Sentence = { en: string; hi: string }

export function coverStatusText(status: MockCoverStatus, premiumDue: boolean, cover: StoredCover | null): Sentence {
  if (cover === null || status === 'NONE') return { en: 'No cover yet', hi: 'अभी कवर नहीं है' }
  if (status === 'WAITING') return { en: `Your cover starts on ${dateEn(cover.starts_on)}.`, hi: `आपका कवर ${dateHi(cover.starts_on)} से शुरू होगा।` }
  if (premiumDue || cover.prepaid_through === null) {
    return {
      en: "Your cover is active, but the premium for the coming days hasn't been paid yet.",
      hi: 'आपका कवर चालू है, पर आगे के दिनों का प्रीमियम अभी जमा नहीं है।',
    }
  }
  return {
    en: `Your cover is active. Premium is paid through ${dateEn(cover.prepaid_through)}.`,
    hi: `आपका कवर चालू है। प्रीमियम ${dateHi(cover.prepaid_through)} तक जमा है।`,
  }
}

/** Credited payouts of this load. The mock has no earlier history, so the rolling 365 days are this replay's day. */
function claimedPaise(rt: MockRuntime, merchantId: string): number {
  return rt.payouts.filter((p) => p.merchant_id === merchantId && p.status === 'CREDITED').reduce((sum, p) => sum + p.amount_paise, 0)
}

export function coverView(rt: MockRuntime, merchant: MockMerchant): Cover {
  const cover = storedCover(rt, merchant.id)
  const { status, premium_due } = deriveCover(cover, rt.nowIso.slice(0, 10))
  const text = coverStatusText(status, premium_due, cover)
  const perDay = cover?.premium_per_day_paise ?? zonePremiumPaise(merchant.zone_id)
  const limit = POLICY_RULES.annual_limit_rupees * PAISE_PER_RUPEE
  const claimed = cover === null ? null : claimedPaise(rt, merchant.id)
  const remaining = claimed === null ? null : Math.max(0, limit - claimed)
  const alert = alertFor(rt.scenario, merchant.zone_id, rt.nowIso)
  const alertActive = alert !== null && alertValidAt(alert, rt.nowIso)
  return {
    merchant_id: merchant.id,
    cover_id: cover?.id ?? null,
    status,
    status_text_hi: text.hi,
    status_text_en: text.en,
    zone_id: merchant.zone_id,
    zone_name: rt.zones.find((z) => z.id === merchant.zone_id)?.name ?? merchant.zone_id,
    purchased_at: cover?.purchased_at ?? null,
    starts_on: cover?.starts_on ?? null,
    prepaid_through: cover?.prepaid_through ?? null,
    waiting_period_days: POLICY_RULES.cover.waiting_period_days,
    premium_per_day_paise: perDay,
    premium_per_day_label: formatInr(perDay),
    premium_due,
    annual_limit_paise: cover === null ? null : limit,
    annual_limit_label: cover === null ? null : formatInr(limit),
    amount_claimed_paise: claimed,
    amount_claimed_label: claimed === null ? null : formatInr(claimed),
    amount_remaining_paise: remaining,
    amount_remaining_label: remaining === null ? null : formatInr(remaining),
    alert_active: alertActive,
    alert_id: alertActive && alert ? alert.id : null,
  }
}

export const COVER_ROUTES: readonly Route[] = [
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/cover$/, handler: (c) => ok(coverView(c.backend.runtime, merchantParam(c))) },
]

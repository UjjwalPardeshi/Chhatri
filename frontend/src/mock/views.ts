/**
 * Mock views: the only place mock runtime state becomes SPEC §19.2 JSON (mirrors
 * `chhatri/replay/views.py`). Zone panel rows are the exact deck strings of SPEC §17.2.
 */
import type { Feature, FeatureCollection } from 'geojson'

import type { ClockState, MerchantDetail, StateSnapshot, ZonePanel, ZoneSnapshot } from '../api/types'
import { formatInr } from '../lib/money'
import { hhmm, weekdayDayLabel } from '../lib/time'
import { ZONE_PAYOUTS } from './area'
import { PAYOUT_RAIL_DELAY_MIN } from './claims'
import { deriveCover, storedCover } from './endpoints/cover'
import { LENDER_NAME, MERCHANTS, type MockMerchant } from './fixtures'
import type { MockRuntime } from './runtime'
import { hhmmOf, hourlyIndex, isoAt, isoPlusMinutes } from './scenarios'
import {
  alertFor,
  alertValidAt,
  hexValue,
  hoursBelow,
  liveIndex,
  windowIndex,
  zoneLabel,
  zoneLowerBound,
  zoneStatus,
  type ZoneMeta,
} from './zones'

const HOUR = 60
/** Newest feed items kept in the snapshot (SPEC §19.2 StateSnapshot.feed). */
const FEED_LIMIT = 60
export const CITY = 'Mumbai'

export type MockGeo = { zones: FeatureCollection; hexes: FeatureCollection; hexIndex: readonly { h3: string; zone_id: string; shops: number }[] }

export function makeGeo(zones: FeatureCollection, hexes: FeatureCollection): MockGeo {
  const hexIndex = hexes.features.map((f) => ({ h3: String(f.properties?.h3), zone_id: String(f.properties?.zone_id), shops: Number(f.properties?.shops ?? 0) }))
  return { zones, hexes, hexIndex }
}

export function zoneMetas(zones: FeatureCollection): ZoneMeta[] {
  return zones.features.map((f) => {
    const p = f.properties ?? {}
    return { id: String(p.id), ward: String(p.ward), name: String(p.name), shops: Number(p.shops) }
  })
}

export function clockView(rt: MockRuntime): ClockState {
  const s = rt.scenario
  return {
    now: rt.nowIso,
    scenario: s.name,
    scenario_title: s.title,
    running: rt.running,
    speed: rt.speed,
    start: isoAt(s.day, s.startMin),
    end: isoAt(s.day, s.endMin),
    label: `${CITY} · ${s.name.replaceAll('_', ' ')} replay · ${hhmmOf(rt.minute)} · simulated`,
  }
}

export function zoneSnapshot(rt: MockRuntime, zone: ZoneMeta): ZoneSnapshot {
  const s = rt.scenario
  const hour = Math.floor(rt.minute / HOUR)
  const alert = alertFor(s, zone.id, rt.nowIso)
  const index = windowIndex(s, zone.id, hour)
  const live = liveIndex(s, zone.id, rt.minute)
  const below = hoursBelow(s, zone.id, rt.minute)
  const trigger = rt.triggers.find((t) => t.zone_id === zone.id) ?? null
  const status = zoneStatus({
    triggered: trigger !== null,
    alertActive: alertValidAt(alert, rt.nowIso),
    hoursBelow: below,
    windowPct: index,
    lastHourPct: hourlyIndex(s, zone.id, hour - 1),
    lowerBoundPct: zoneLowerBound(zone.id),
    shops: zone.shops,
  })
  return {
    zone_id: zone.id,
    ward: zone.ward,
    name: zone.name,
    shops: zone.shops,
    index_pct: index,
    live_index_pct: live,
    lower_bound_pct: zoneLowerBound(zone.id),
    status,
    hours_below: below,
    alert: alert && { id: alert.id, level: alert.level, kind: alert.kind, valid_from: alert.valid_from, valid_to: alert.valid_to, headline_en: alert.headline_en },
    label: zoneLabel(zone.id, trigger ? trigger.index_pct : live, zone.shops),
  }
}

export function hexesView(rt: MockRuntime, geo: MockGeo): Record<string, number | null> {
  const live = new Map(rt.zones.map((z) => [z.id, liveIndex(rt.scenario, z.id, rt.minute)]))
  return Object.fromEntries(geo.hexIndex.map((h) => [h.h3, hexValue(live.get(h.zone_id) ?? null, h.h3, h.shops)]))
}

/** B3: ward polygons of zones with rain in the current hour, else null. */
export function rainBand(rt: MockRuntime, geo: MockGeo): FeatureCollection | null {
  const hour = Math.floor(rt.minute / HOUR)
  if (!rt.scenario.rainHours.includes(hour)) return null
  const features: Feature[] = geo.zones.features.filter((f) => rt.scenario.rainZones.includes(String(f.properties?.id)))
  return { type: 'FeatureCollection', features }
}

export function snapshotView(rt: MockRuntime, geo: MockGeo): StateSnapshot {
  return {
    clock: clockView(rt),
    zones: rt.zones.map((z) => zoneSnapshot(rt, z)),
    hexes: hexesView(rt, geo),
    kpis: rt.kpis,
    triggers: rt.triggers,
    explanations: rt.explanations,
    feed: rt.feed.toReversed().slice(0, FEED_LIMIT),
    demo_merchant_id: rt.scenario.demoMerchantId,
    rain_band: rainBand(rt, geo),
  }
}

/** "Red alert from 14:00" (same day) or "Red alert from Tue 14:00" (a coming day). */
export function alertRow(alert: ReturnType<typeof alertFor>, day: string): string {
  if (!alert) return 'No weather alert'
  const level = alert.level.charAt(0) + alert.level.slice(1).toLowerCase()
  const when = alert.valid_from.startsWith(day) ? hhmm(alert.valid_from) : `${weekdayDayLabel(alert.valid_from).slice(0, 3)} ${hhmm(alert.valid_from)}`
  return `${level} alert from ${when}`
}

export function zonePanelView(rt: MockRuntime, zone: ZoneMeta): ZonePanel {
  const snapshot = zoneSnapshot(rt, zone)
  const trigger = rt.triggers.find((t) => t.zone_id === zone.id) ?? null
  const totals = rt.zoneTotals.get(zone.id) ?? null
  const salesPct = trigger ? trigger.index_pct : snapshot.index_pct
  const rows: ZonePanel['rows'] = [
    { label: 'Alert', value: alertRow(alertFor(rt.scenario, zone.id, rt.nowIso), rt.scenario.day) },
    { label: 'Sales', value: `${salesPct}% of expected for 3 hours` },
    { label: 'Cover', value: `${zone.shops} of ${zone.shops} prepaid` },
  ]
  if (trigger && totals) {
    const due = isoPlusMinutes(rt.scenario.day, totals.decidedMin, PAYOUT_RAIL_DELAY_MIN)
    rows.push({ label: 'Paid', value: totals.creditedAt ? `${totals.creditedAt.slice(11, 16)}, with the settlement` : `Due ${due.slice(11, 16)}, with the settlement` })
    const total = formatInr(totals.creditedAt ? totals.paidPaise : ZONE_PAYOUTS[zone.id]?.totalPaise ?? 0)
    rows.push({ label: 'Total', value: totals.paused > 0 ? `${total} · instalments paused` : total })
  }
  const completed = Math.floor(rt.minute / HOUR)
  const firstHour = Math.floor(rt.scenario.startMin / HOUR)
  const hourly = Array.from({ length: Math.max(0, completed - firstHour) }, (_, i) => ({
    hour: isoAt(rt.scenario.day, (firstHour + i) * HOUR),
    index_pct: hourlyIndex(rt.scenario, zone.id, firstHour + i),
  }))
  return {
    zone: snapshot,
    triggered: trigger !== null,
    rows,
    explanation: rt.explanations[zone.id] ?? null,
    shops_paid: totals?.creditedAt ? totals.shops : 0,
    total_paid_paise: totals?.paidPaise ?? 0,
    total_paid_label: formatInr(totals?.paidPaise ?? 0),
    hourly,
  }
}

/** The console's cover line: the stored cover (Anil's seeded pilot cover, or one bought through a link), priced by zone. */
function coverBlock(rt: MockRuntime, merchantId: string, perDayPaise: number): MerchantDetail['cover'] {
  const cover = storedCover(rt, merchantId)
  if (cover === null) return null
  const { status } = deriveCover(cover, rt.nowIso.slice(0, 10))
  return { status, starts_on: cover.starts_on, prepaid_through: cover.prepaid_through ?? cover.starts_on, premium_per_day_label: formatInr(cover.premium_per_day_paise ?? perDayPaise) }
}

export function merchantDetailView(rt: MockRuntime, merchant: MockMerchant): MerchantDetail {
  const { owner_first_en: _first, kyc_name: _kyc, expected_day_paise, instalment_paise, premium_per_day_paise, ...summary } = merchant
  return {
    ...summary,
    cover: coverBlock(rt, merchant.id, premium_per_day_paise),
    loan: instalment_paise === null ? null : { daily_instalment_label: formatInr(instalment_paise), lender_name: LENDER_NAME },
    expected_today_label: formatInr(expected_day_paise),
    payouts: rt.payouts.filter((p) => p.merchant_id === merchant.id),
    decisions: rt.decisions.filter((d) => d.merchant_id === merchant.id),
    holiday_requests: rt.holidayRequests.filter((r) => r.merchant_id === merchant.id).map(({ merchant_id: _owner, ...row }) => row),
  }
}

export function merchantSummaries() {
  return Object.values(MERCHANTS).map((m) => ({
    id: m.id,
    shop_name: m.shop_name,
    owner_name: m.owner_name,
    zone_id: m.zone_id,
    shop_type: m.shop_type,
    lat: m.lat,
    lng: m.lng,
    is_demo: m.is_demo,
    covered: m.covered,
  }))
}

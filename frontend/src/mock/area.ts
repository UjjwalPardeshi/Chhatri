/**
 * Mock area detection and area claims (SPEC §8.2, §13.5 "Area payout", §17.2). At each hour
 * boundary every zone is tested against the four trigger conditions; a firing zone gets its
 * decisions at once, its credits at +4 min and its instalment pauses at +5 min (B1/B2).
 * The demo merchant gets a full Decision/Payout/Pause and WhatsApp + Soundbox messages; the other
 * shops of a zone are carried as zone totals (the per-zone amounts are the calibrated targets).
 */
import type { AreaTrigger } from '../api/types'
import { formatInr } from '../lib/money'
import { hhmm } from '../lib/time'
import { MSG } from './catalogue'
import { areaExplanation, check, decide, holidaysGranted, INSTALMENT_PAUSE_DELAY_MIN, PAYOUT_RAIL_DELAY_MIN, schedulePayout } from './claims'
import { storedCover } from './endpoints/cover'
import { MERCHANTS, POLICY_RULES, type MockMerchant } from './fixtures'
import type { MockRuntime } from './runtime'
import { hourlyIndex, isoAt } from './scenarios'
import {
  alertCoversWindow,
  alertFor,
  alertValidAt,
  hoursBelow,
  INDEX_FLOOR_PCT,
  MIN_SHOPS_IN_INDEX,
  WINDOW_HOURS,
  windowIndex,
  zoneLowerBound,
  type ZoneMeta,
} from './zones'

const HOUR = 60

/** Zone payout totals and loans for the monsoon triggers, as the live backend plays them (₹4,25,420 over 312 shops, 123 instalments; Z7 = ₹58,900, SPEC §17.2). */
export const ZONE_PAYOUTS: Readonly<Record<string, { totalPaise: number; loans: number }>> = Object.freeze({
  Z7: { totalPaise: 5_890_000, loans: 19 },
  Z3: { totalPaise: 20_671_900, loans: 50 },
  Z12: { totalPaise: 15_980_100, loans: 54 },
})

export function zoneNumber(zoneId: string): string {
  return zoneId.replace(/^Z/, '')
}

export function slowDayExplanation(zoneId: string, pct: number): string {
  return `Why Zone ${zoneNumber(zoneId)} got nothing: its sales fell to ${pct}% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay.`
}

function hourlyWindow(rt: MockRuntime, zoneId: string, hour: number): number[] {
  const out: number[] = []
  for (let h = hour - WINDOW_HOURS; h < hour; h++) out.push(hourlyIndex(rt.scenario, zoneId, h))
  return out
}

function shouldTrigger(rt: MockRuntime, zone: ZoneMeta, hour: number): boolean {
  if (rt.triggers.some((t) => t.zone_id === zone.id)) return false
  const alert = alertFor(rt.scenario, zone.id, rt.nowIso)
  const start = isoAt(rt.scenario.day, (hour - WINDOW_HOURS) * HOUR)
  if (!alertCoversWindow(alert, start, rt.nowIso)) return false
  const hourly = hourlyWindow(rt, zone.id, hour)
  if (!hourly.every((pct) => pct < INDEX_FLOOR_PCT)) return false
  return windowIndex(rt.scenario, zone.id, hour) < zoneLowerBound(zone.id) && zone.shops >= MIN_SHOPS_IN_INDEX
}

/** Hour-boundary detection (SPEC §17.1 on_hour). */
export function onHour(rt: MockRuntime): void {
  const hour = rt.minute / HOUR
  if (rt.scenario.rainHours[0] === hour) {
    rt.addFeed('weather', `Heavy rain band over ${rt.scenario.rainZones.join(', ')} · red alert now active`)
  }
  for (const zone of rt.zones) {
    if (shouldTrigger(rt, zone, hour)) fireTrigger(rt, zone, hour)
    else noteZone(rt, zone, hour)
  }
}

function noteZone(rt: MockRuntime, zone: ZoneMeta, hour: number): void {
  const alert = alertFor(rt.scenario, zone.id, rt.nowIso)
  const below = hoursBelow(rt.scenario, zone.id, rt.minute)
  const win = windowIndex(rt.scenario, zone.id, hour)
  if (alertValidAt(alert, rt.nowIso) && below > 0 && below < WINDOW_HOURS) {
    rt.addFeed('watch', `${zone.id} below ${INDEX_FLOOR_PCT}% of expected for ${below} h · alert active`, { zone_id: zone.id })
  }
  if (!alert && win < zoneLowerBound(zone.id)) {
    if (!(zone.id in rt.explanations)) {
      rt.addFeed('slow_day', `${zone.id} at ${win}% with no alert: slow day, no payout`, { zone_id: zone.id })
    }
    rt.explanations = { ...rt.explanations, [zone.id]: slowDayExplanation(zone.id, win) }
  }
}

function fireTrigger(rt: MockRuntime, zone: ZoneMeta, hour: number): void {
  const alert = alertFor(rt.scenario, zone.id, rt.nowIso)
  const payouts = ZONE_PAYOUTS[zone.id]
  if (!alert || !payouts) throw new Error(`mock has no payout script for a trigger in ${zone.id}`)
  const win = windowIndex(rt.scenario, zone.id, hour)
  const trigger: AreaTrigger = {
    id: `E-${zone.id}-${rt.scenario.day.replaceAll('-', '')}`,
    zone_id: zone.id,
    alert_id: alert.id,
    window_start: isoAt(rt.scenario.day, (hour - WINDOW_HOURS) * HOUR),
    window_end: rt.nowIso,
    index_pct: win,
    drop_pct: 100 - win,
    hourly_index_pct: hourlyWindow(rt, zone.id, hour),
    lower_bound_pct: zoneLowerBound(zone.id),
    shops_in_index: zone.shops,
    fired_at: rt.nowIso,
  }
  rt.triggers = [...rt.triggers, trigger]
  rt.emit('trigger', { trigger })
  rt.record('system', 'trigger.fired', 'trigger', trigger.id, { index_pct: win, hourly_index_pct: trigger.hourly_index_pct, shops_in_index: zone.shops })
  rt.addFeed('trigger', `${zone.id} triggered · ${win}% of expected for 3 h · ${zone.shops} shops`, { zone_id: zone.id })
  rt.setKpis({ zones_triggered: rt.kpis.zones_triggered + 1 })
  rt.zoneTotals.set(zone.id, { shops: zone.shops, decidedMin: rt.minute, paidPaise: 0, creditedAt: null, paused: 0 })
  rt.record('policy-engine', 'claims.area_batch', 'zone', zone.id, { approved: zone.shops, amount_paise: payouts.totalPaise })
  rt.addFeed('decision', `Policy engine approved ${zone.shops} area payouts in ${zone.id} · ${formatInr(payouts.totalPaise)}`, { zone_id: zone.id })
  const demo = Object.values(MERCHANTS).find((m) => m.zone_id === zone.id && m.covered)
  if (demo) decideDemoMerchant(rt, demo, trigger)
  scheduleZoneTotals(rt, zone, payouts)
}

function scheduleZoneTotals(rt: MockRuntime, zone: ZoneMeta, payouts: { totalPaise: number; loans: number }): void {
  const decided = rt.minute
  rt.schedule(decided + PAYOUT_RAIL_DELAY_MIN, 'credit_zone', () => {
    const totals = rt.zoneTotals.get(zone.id)
    if (!totals) throw new Error(`zone totals missing for ${zone.id}`)
    rt.zoneTotals.set(zone.id, { ...totals, paidPaise: payouts.totalPaise, creditedAt: rt.nowIso })
    rt.setKpis({
      shops_paid: rt.kpis.shops_paid + zone.shops,
      total_paid_paise: rt.kpis.total_paid_paise + payouts.totalPaise,
      trigger_to_money_min: PAYOUT_RAIL_DELAY_MIN,
    })
    rt.addFeed('payout', `${formatInr(payouts.totalPaise)} credited to ${zone.shops} shops in ${zone.id} with the settlement`, { zone_id: zone.id })
  })
  rt.schedule(decided + INSTALMENT_PAUSE_DELAY_MIN, 'pause_zone', () => {
    const totals = rt.zoneTotals.get(zone.id)
    if (!totals) throw new Error(`zone totals missing for ${zone.id}`)
    const granted = holidaysGranted(rt, payouts.loans)
    rt.zoneTotals.set(zone.id, { ...totals, paused: granted })
    rt.setKpis({ instalments_paused: rt.kpis.instalments_paused + granted })
    if (granted < payouts.loans) rt.addFeed('holiday', `${payouts.loans} holiday requests got no answer from the lender in ${zone.id} · the instalments stay due`, { zone_id: zone.id })
    else rt.addFeed('instalment', `${payouts.loans} loan instalments paused in ${zone.id} · lender notified`, { zone_id: zone.id })
  })
}

const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2025-03-17" to "17 Mar 2025", the way the backend's check text writes a date. */
function shortDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return `${day} ${SHORT_MONTHS[month - 1]} ${year}`
}

const shortDateTime = (iso: string): string => `${shortDate(iso)} ${hhmm(iso)}`

/**
 * The nine HARD checks of an area claim, in the backend's order and wording (`policy/checks.py`), with the values of
 * the mock's own records. Anil's cover facts are the seeded pilot cover's, so the console and the receipt agree.
 */
function areaChecks(rt: MockRuntime, merchant: MockMerchant, trigger: AreaTrigger) {
  const cover = storedCover(rt, merchant.id)
  const alert = alertFor(rt.scenario, trigger.zone_id, trigger.fired_at)
  const hourly = trigger.hourly_index_pct.map((p) => `${p}%`).join(' · ')
  const event = trigger.window_end.slice(0, 10)
  const through = cover?.prepaid_through ? shortDate(cover.prepaid_through) : 'not paid'
  const window = `${shortDateTime(trigger.window_start)}–${hhmm(trigger.window_end)}`
  const alertSpan = alert ? `${alert.id} ${shortDateTime(alert.valid_from)}–${shortDateTime(alert.valid_to)}` : 'no alert'
  return [
    check('COVER_IN_FORCE', 'HARD', 'PASS', 'Cover in force', `ACTIVE since ${cover ? shortDate(cover.starts_on) : 'never'}`, 'ACTIVE on event date', 'Cover was active on the event date.'),
    check('PREMIUM_PREPAID', 'HARD', 'PASS', 'Premium prepaid', `Prepaid through ${through}`, `Prepaid through ${shortDate(event)} or later`, `Premium received in advance through ${through}.`),
    check('COVER_BEFORE_ALERT', 'HARD', 'PASS', 'Cover bought before the alert', `Bought ${cover ? shortDate(cover.purchased_at) : 'never'}`, `Before ${alert ? shortDateTime(alert.issued_at) : 'the alert'}`, 'Cover was bought before the alert was issued.'),
    check('ALERT_ACTIVE', 'HARD', 'PASS', 'Alert active for the whole window', alertSpan, `Alert for ${trigger.zone_id} ${window}`, `${alert ? `${alert.level.charAt(0)}${alert.level.slice(1).toLowerCase()} ${alert.kind.toLowerCase()} alert` : 'The alert'} covers the whole window.`),
    check('INDEX_QUORUM', 'HARD', 'PASS', 'Enough shops in the index', `${trigger.shops_in_index} shops`, `At least ${MIN_SHOPS_IN_INDEX} shops`, `${trigger.shops_in_index} shops are in the zone index.`),
    check('BELOW_FLOOR', 'HARD', 'PASS', 'Every hour below the floor', hourly, `All ${WINDOW_HOURS} hours below ${INDEX_FLOOR_PCT}%`, `Sales stayed below ${INDEX_FLOOR_PCT}% of expected in each of the ${WINDOW_HOURS} hours.`),
    check('BELOW_MODEL_RANGE', 'HARD', 'PASS', "Below the model's range", `${trigger.index_pct}%`, `Below ${trigger.lower_bound_pct}%`, "The window index is below the zone's lower bound."),
    check('NOT_ALREADY_PAID', 'HARD', 'PASS', 'Not already paid', 'No payout today', 'None', 'No payout for this merchant, date and kind.'),
    check('WITHIN_ANNUAL_LIMIT', 'HARD', 'PASS', 'Within the annual limit', `${formatInr(0)} paid this year`, `At most ${formatInr(POLICY_RULES.annual_limit_rupees * 100)}`, 'Paid in the rolling year plus this amount stays within the limit.'),
  ]
}

/**
 * Anil's claim, decision and payout are number 142, as in the backend: it decides the zones in order, and the 141
 * shops of Z3 come first (data-model 5.1, fs-03). The mock decides only the demo merchant, so it moves its counters on.
 */
const DEMO_RECORD_NUMBER = 142

function decideDemoMerchant(rt: MockRuntime, merchant: MockMerchant, trigger: AreaTrigger): void {
  for (const prefix of ['CL', 'D', 'P']) rt.advanceIds(prefix, DEMO_RECORD_NUMBER - 1)
  const claimId = rt.nextId('CL')
  const decision = decide(rt, {
    claimId,
    merchantId: merchant.id,
    checks: areaChecks(rt, merchant, trigger),
    explanation: areaExplanation(rt.scenario.day, merchant.expected_day_paise, trigger.drop_pct),
    decidedBy: 'policy-engine',
    referral: null,
  })
  schedulePayout(rt, decision, merchant, {
    onCredited: (payout) => {
      rt.send(merchant.id, { kind: 'TEXT', text: MSG.areaPayoutIntro(merchant.owner_name_hi, merchant.owner_first_en, trigger.drop_pct) })
      rt.send(merchant.id, { kind: 'PAYOUT_CARD', text: null, card: { amount_label: payout.amount_label, subtitle_hi: MSG.payoutCard.hi, subtitle_en: MSG.payoutCard.en, badge: MSG.payoutCard.badge } })
      announceSoundbox(rt, merchant, payout.amount_label)
    },
    onPaused: (text) => {
      rt.send(merchant.id, { kind: 'TEXT', text })
    },
  })
}

export function announceSoundbox(rt: MockRuntime, merchant: MockMerchant, amountLabel: string): void {
  const text = MSG.soundbox(amountLabel)
  rt.send(merchant.id, { kind: 'SOUNDBOX', channel: 'SOUNDBOX', text })
  rt.emit('soundbox', { merchant_id: merchant.id, text: text.hi ?? text.en, amount_label: amountLabel, audio_url: null })
  rt.addFeed('soundbox', `Soundbox at ${merchant.shop_name}: "${text.hi}"`, { merchant_id: merchant.id })
}

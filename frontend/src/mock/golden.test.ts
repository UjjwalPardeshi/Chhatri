/** SPEC §17.2 monsoon golden numbers and strings, reproduced by the mock (acceptance item 11). */
import { afterEach, describe, expect, it } from 'vitest'

import type { MockBackend } from './backend'
import { testBackend } from './testkit'
import { snapshotView, zonePanelView } from './views'

let backend: MockBackend
afterEach(() => backend?.dispose())

function at(time: string) {
  backend = testBackend()
  backend.seek(time)
  return backend
}

describe('monsoon at 17:00', () => {
  it('fires Z3, Z7, Z12 with the calibrated windows and explains Z9', () => {
    const rt = at('17:00').runtime
    const byZone = Object.fromEntries(rt.triggers.map((t) => [t.zone_id, t]))
    expect(Object.keys(byZone).toSorted()).toEqual(['Z12', 'Z3', 'Z7'])
    expect([byZone.Z7.index_pct, byZone.Z7.drop_pct]).toEqual([37, 63])
    expect(byZone.Z3.index_pct).toBe(38)
    expect(byZone.Z12.index_pct).toBe(47)
    expect(byZone.Z7.hourly_index_pct.every((p) => p < 50)).toBe(true)
    expect(byZone.Z7.window_start).toBe('2025-08-19T14:00:00+05:30')
    expect(byZone.Z7.fired_at).toBe('2025-08-19T17:00:00+05:30')
    const snap = snapshotView(rt, backend.geo)
    expect(snap.clock.label).toBe('Mumbai · monsoon replay · 17:00 · simulated')
    const z9 = snap.zones.find((z) => z.zone_id === 'Z9')
    expect([z9?.status, z9?.index_pct, z9?.alert]).toEqual(['slow_day', 61, null])
    expect(snap.explanations.Z9).toBe(
      "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay.",
    )
    const z7 = snap.zones.find((z) => z.zone_id === 'Z7')
    expect(z7?.label).toBe('Z7 · 37% · 46 shops')
    expect(snap.zones.find((z) => z.zone_id === 'Z3')?.label).toBe('Z3 · 38% · 141 shops')
    expect(snap.zones.find((z) => z.zone_id === 'Z12')?.label).toBe('Z12 · 47% · 125 shops')
    expect(snap.kpis).toMatchObject({ zones_triggered: 3, shops_paid: 0, trigger_to_money_min: null })
    expect(snap.rain_band?.features.map((f) => f.properties?.id).toSorted()).toEqual(['Z12', 'Z3', 'Z7'])
  })

  it('does not trigger before the alert covers a full 3-hour window', () => {
    const rt = at('16:59').runtime
    expect(rt.triggers).toEqual([])
    expect(snapshotView(rt, backend.geo).zones.find((z) => z.zone_id === 'Z7')?.status).toBe('watch')
  })
})

describe('monsoon at 17:05', () => {
  it('pays 312 shops in 4 minutes and pauses instalments at 17:05', () => {
    const rt = at('17:05').runtime
    expect(rt.kpis).toMatchObject({ zones_triggered: 3, shops_paid: 312, trigger_to_money_min: 4, instalments_paused: 124 })
    const anil = rt.payouts.filter((p) => p.merchant_id === 'S-0142')
    expect(anil).toHaveLength(1)
    expect(anil[0]).toMatchObject({ amount_label: '₹1,380', status: 'CREDITED', credited_at: '2025-08-19T17:04:00+05:30', rail: 'Paytm settlement (simulated)' })
    expect(rt.pauses[0]).toMatchObject({ amount_label: '₹600', instalment_date: '2025-08-20', created_at: '2025-08-19T17:05:00+05:30' })
    const decision = rt.decisions[0]
    expect(decision.outcome).toBe('APPROVED')
    expect(decision.decided_at).toBe('2025-08-19T17:00:00+05:30')
    expect(decision.explanation).toMatchObject({ expected_day_label: '₹4,380', drop_pct: 63, formula_en: '½ × ₹4,380 × 63% = ₹1,380', formula_hi: '₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380' })
  })

  it('shows the exact Z7 panel rows (SPEC §17.2)', () => {
    const rt = at('17:05').runtime
    const z7 = rt.zones.find((z) => z.id === 'Z7')
    if (!z7) throw new Error('Z7 missing')
    const panel = zonePanelView(rt, z7)
    expect(panel.rows).toEqual([
      { label: 'Alert', value: 'Red alert from 14:00' },
      { label: 'Sales', value: '37% of expected for 3 hours' },
      { label: 'Cover', value: '46 of 46 prepaid' },
      { label: 'Paid', value: '17:04, with the settlement' },
      { label: 'Total', value: '₹58,900 · instalments paused' },
    ])
    expect(panel).toMatchObject({ triggered: true, shops_paid: 46, total_paid_label: '₹58,900' })
  })

  it('sends the deck messages in order (SPEC §13.5 area payout flow)', () => {
    const rt = at('17:05').runtime
    const anil = rt.messages.filter((m) => m.merchant_id === 'S-0142')
    expect(anil.map((m) => [m.kind, m.created_at.slice(11, 16)])).toEqual([
      ['TEXT', '17:04'],
      ['PAYOUT_CARD', '17:04'],
      ['SOUNDBOX', '17:04'],
      ['TEXT', '17:05'],
    ])
    expect(anil[0].text_hi).toBe('अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।')
    expect(anil[0].text_en).toBe("Anil ji, heavy rain cut your area's sales by 63% today.")
    expect(anil[1].card).toEqual({ amount_label: '₹1,380', subtitle_hi: 'आज के सेटलमेंट के साथ जमा', subtitle_en: "Credited with today's settlement", badge: 'No claim needed' })
    expect(anil[2].text_hi).toBe('Paytm par ₹1,380 prapt hue — Chhatri se')
    expect(anil[3].text_hi).toBe('कल की ₹600 की किस्त रोक दी गई है।')
    expect(anil[3].text_en).toBe("Tomorrow's ₹600 instalment is paused.")
  })

  it('reports 17:04 in the Paid row only after the credit', () => {
    const rt = at('17:02').runtime
    const z7 = rt.zones.find((z) => z.id === 'Z7')
    if (!z7) throw new Error('Z7 missing')
    expect(zonePanelView(rt, z7).rows.slice(3)).toEqual([
      { label: 'Paid', value: 'Due 17:04, with the settlement' },
      { label: 'Total', value: '₹58,900' },
    ])
  })
})

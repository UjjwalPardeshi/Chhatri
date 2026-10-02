/** Live panel helpers (SPEC §19.2 FeedItem, §17.2 zone headline, §19.1 payout toast). */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import type { FeedItem, StateSnapshot } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { snapshotView } from '../../mock/views'
import { feedRows, keyFigure, type FeedRow } from './feedGroups'
import { toastText } from './PayoutToast'
import { nextHour, trendFromPanel, zoneTrend } from './zoneTrend'

let backend: MockBackend
let snapshot: StateSnapshot
beforeEach(() => {
  backend = testBackend()
  backend.seek('17:05')
  snapshot = snapshotView(backend.runtime, backend.geo)
})
afterEach(() => backend.dispose())

function summary(row: FeedRow): string {
  return row.kind === 'group' ? `${row.title}: ${row.parts.map((p) => `${p.zone} ${p.figure}`).join(', ')}` : row.text
}

const watch = (zone: string, id: number) => ({ id, at: '2025-08-19T16:00:00+05:30', type: 'watch', text_en: `${zone} below 60% of expected for 2 h · alert active`, zone_id: zone }) as FeedItem

describe('feed grouping', () => {
  it('words the watch title from the published floor, not a copied 50', () => {
    const rows = feedRows([watch('Z3', 1), watch('Z7', 2)], 60)
    expect(rows[0]).toMatchObject({ kind: 'group', title: 'Below 60% of expected, alert active' })
  })

  it('folds the per-zone lines of one minute into story rows, newest first', () => {
    const rows = feedRows(snapshot.feed).slice(0, 5).map(summary)
    expect(rows).toEqual([
      'Loan instalments paused: Z3 50, Z7 19, Z12 54',
      'Area payouts credited: Z3 ₹2,06,719, Z7 ₹58,900, Z12 ₹1,59,801',
      'Soundbox at Anil\'s Tea Stall: "Paytm par ₹1,380 prapt hue — Chhatri se"',
      'Area payouts approved: Z3 ₹2,06,719, Z7 ₹58,900, Z12 ₹1,59,801',
      'Area triggers fired: Z3 38%, Z7 37%, Z12 47%',
    ])
  })

  it('keeps single lines, lines without zones and repeated zones unfolded', () => {
    const at = '2025-08-19T12:00:00+05:30'
    const items: FeedItem[] = [
      { id: 1, at, type: 'trigger', text_en: 'Z7 triggered · 37%', zone_id: 'Z7' },
      { id: 2, at, type: 'trigger', text_en: 'Z7 triggered again · 36%', zone_id: 'Z7' },
      { id: 3, at, type: 'scenario', text_en: 'Scenario loaded' },
    ]
    expect(feedRows(items).map((r) => r.kind)).toEqual(['item', 'item', 'item'])
    expect(feedRows([items[0]])[0]).toMatchObject({ kind: 'item', text: 'Z7 triggered · 37%' })
  })

  it('picks the figure that matters for each line type', () => {
    expect(keyFigure('payout', '₹58,900 credited to 46 shops in Z7')).toBe('₹58,900')
    expect(keyFigure('instalment', '18 loan instalments paused in Z7')).toBe('18')
    expect(keyFigure('watch', 'Z12 below 50% of expected for 2 h · alert active')).toBe('2 h')
    expect(keyFigure('trigger', 'Z3 triggered · 38% of expected')).toBe('38%')
    expect(keyFigure('other', 'nothing to see')).toBeNull()
  })
})

describe('zone headline', () => {
  it('uses the trigger for a triggered zone and the trailing hours otherwise', () => {
    const z7 = snapshot.triggers.find((t) => t.zone_id === 'Z7')
    expect(z7).toBeTruthy()
    const panel = { zone: { ...snapshot.zones[0], zone_id: 'Z7', index_pct: 99 }, hourly: [] }
    expect(zoneTrend(panel, snapshot.triggers)).toEqual({
      pct: 37,
      hours: [
        { label: '14:00', pct: 41 },
        { label: '15:00', pct: 36 },
        { label: '16:00', pct: 34 },
      ],
      window: '14:00 to 17:00',
    })
    const hourly = [9, 10, 11, 12].map((h) => ({ hour: `2025-08-19T${String(h).padStart(2, '0')}:00:00+05:30`, index_pct: h === 12 ? null : h * 5 }))
    const quiet = trendFromPanel({ zone: { ...snapshot.zones[0], index_pct: 50 }, hourly } as unknown as Parameters<typeof trendFromPanel>[0])
    expect(quiet).toEqual({ pct: 50, hours: [{ label: '09:00', pct: 45 }, { label: '10:00', pct: 50 }, { label: '11:00', pct: 55 }], window: '09:00 to 12:00' })
    expect(trendFromPanel({ zone: { ...snapshot.zones[0], index_pct: null }, hourly: [] })).toBeNull()
    expect(nextHour('23:00')).toBe('00:00')
    expect(nextHour('late')).toBe('late')
  })
})

describe('payout toast', () => {
  it('reads the amount and credit time from the payout', () => {
    expect(toastText({ amount_label: '₹1,380', credited_at: '2025-08-19T17:04:00+05:30' })).toBe('₹1,380 credited · 17:04')
  })
})

/** Live map (SPEC §20 "Live map", B3): labels, pin caption, rain caption, tiles and clicks. */
import { fireEvent, render, waitFor } from '@testing-library/react'
import type { FeatureCollection } from 'geojson'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MerchantDetail, StateSnapshot } from '../../api/types'
import { CARTO_WATERMARK_SHA256 } from '../../lib/tiles'
import type { MockBackend } from '../../mock/backend'
import { ANIL } from '../../mock/fixtures'
import { testBackend } from '../../mock/testkit'
import { merchantDetailView, snapshotView } from '../../mock/views'
import { centroidsById } from './geo'
import { LiveMap, pinCaption, rainCaption, waterSpecs, zoneLabelSpecs } from './LiveMap'
import { alertStatus, basemapTitle, offlineText } from './overlays'

let backend: MockBackend
let snapshot: StateSnapshot
let anil: MerchantDetail
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  backend = testBackend()
  backend.seek('17:05')
  snapshot = snapshotView(backend.runtime, backend.geo)
  anil = merchantDetailView(backend.runtime, ANIL)
})
afterEach(() => backend.dispose())

describe('map labels', () => {
  it('labels triggered, watch and slow-day zones plus the merchant and selected zones', () => {
    const specs = zoneLabelSpecs(snapshot.zones, centroidsById(backend.geo.zones as FeatureCollection), ['Z1', null])
    const ids = specs.map((s) => s.id)
    expect(ids).toEqual(expect.arrayContaining(['Z3', 'Z7', 'Z12', 'Z9', 'Z1']))
    expect(specs.find((s) => s.id === 'Z7')?.html).toContain('Z7 · 37% · 46 shops')
    expect(specs.find((s) => s.id === 'Z9')?.html).toContain('Slow day, no alert: no payout')
    expect(zoneLabelSpecs(snapshot.zones, new Map(), [])).toEqual([])
    expect(waterSpecs().map((s) => s.movable)).toEqual([false, false])
  })

  it('labels a slow day with the trailing 3-hour index, not the live one (B3: Z9 reads 61% like its explanation)', () => {
    const z9 = snapshot.zones.find((z) => z.zone_id === 'Z9')
    if (!z9) throw new Error('Z9 missing from the mock snapshot')
    const midHour = [{ ...z9, index_pct: 61, live_index_pct: 62 }]
    const [spec] = zoneLabelSpecs(midHour, centroidsById(backend.geo.zones as FeatureCollection), [])
    expect(spec.html).toContain('Z9 · 61% of expected')
    expect(spec.html).not.toContain('62%')
  })

  it('captions the pin by payout state', () => {
    expect(pinCaption(anil, '2025-08-19')).toBe('₹1,380 paid · 17:04')
    expect(pinCaption(anil, '2025-08-20')).toBe('Covered · Z7')
    const pending = { ...anil, payouts: anil.payouts.map((p) => ({ ...p, status: 'PENDING' as const })) }
    expect(pinCaption(pending, '2025-08-19')).toBe('Payout on its way')
    expect(pinCaption({ ...anil, payouts: [], covered: false }, '2025-08-19')).toBe('Not covered · Z7')
  })

  it('captions the rain band with the earliest alert start', () => {
    expect(snapshot.rain_band).not.toBeNull()
    expect(rainCaption(snapshot.zones, snapshot.rain_band as FeatureCollection)).toBe('Heavy rain band · since 14:00')
    expect(rainCaption([], { type: 'FeatureCollection', features: [] })).toBe('Heavy rain band')
  })

  it('explains the tile fallback honestly', () => {
    expect(offlineText('watermark')).toBeNull()
    expect(offlineText('unreachable')).toBe('Basemap offline · wards shown')
    expect(offlineText('errors')).toBe('Basemap offline · wards shown')
    expect(basemapTitle(null)).toBe('Basemap: CARTO Positron')
    expect(basemapTitle('watermark')).toBe('Ward basemap (no CARTO tile key configured)')
    expect(basemapTitle('unreachable')).toBe('Ward basemap (tiles unavailable)')
  })

  it('states the alert in one chip: upcoming, active, triggered, then gone', () => {
    expect(alertStatus(snapshot.zones, snapshot.clock)).toEqual({ tone: 'red', text: 'Red alert · 3 zones triggered', live: true })
    const calm = snapshot.zones.map((z) => ({ ...z, status: 'watch' as const }))
    const alert = snapshot.zones.find((z) => z.alert !== null)?.alert
    expect(alert).toBeTruthy()
    if (!alert) return
    expect(alertStatus(calm, { now: alert.valid_from })?.text).toMatch(/^Red alert active · \d+ zones on watch$/)
    expect(alertStatus(calm, { now: '2025-08-19T00:00:00+05:30' })?.text).toMatch(/^Red alert from 14:00 · \d+ zones$/)
    expect(alertStatus(calm, { now: alert.valid_to })).toBeNull()
    expect(alertStatus(snapshot.zones.map((z) => ({ ...z, alert: null })), snapshot.clock)).toBeNull()
  })
})

const noop = (): void => undefined

function tileResponse(bytes: Uint8Array<ArrayBuffer>): Promise<Response> {
  return Promise.resolve(new Response(bytes, { status: 200 }))
}

function renderMap(props: Partial<Parameters<typeof LiveMap>[0]> = {}) {
  const onSelectZone = vi.fn<(zoneId: string) => void>()
  const onOpenMerchant = vi.fn<(merchantId: string) => void>()
  const geo = { zones: backend.geo.zones as FeatureCollection, hexes: backend.geo.hexes as FeatureCollection }
  const view = render(<LiveMap geo={geo} snapshot={snapshot} merchant={anil} selected="Z7" rule={{ floorPct: 50, hours: 3 }} onSelectZone={onSelectZone} onOpenMerchant={onOpenMerchant} {...props} />)
  return { ...view, onSelectZone, onOpenMerchant }
}

describe('LiveMap', () => {
  it('keeps CARTO tiles when the probe tile is real, and routes label clicks', async () => {
    vi.stubGlobal('fetch', () => tileResponse(new Uint8Array([1, 2, 3])))
    const { onSelectZone, onOpenMerchant, getByTestId } = renderMap()
    await waitFor(() => expect(document.querySelector('.map-tiles')).toBeTruthy())
    expect(getByTestId('live-map').dataset.tiles).toBe('carto')
    fireEvent.click(document.querySelector('.zone-label-icon--slow_day') as Element)
    expect(onSelectZone).toHaveBeenCalledWith('Z9')
    fireEvent.click(document.querySelector('.pin-icon') as Element)
    expect(onOpenMerchant).toHaveBeenCalledWith('S-0142')
    fireEvent.click(document.querySelector('.water-label-icon') as Element)
    expect(document.querySelector('.rain-label')?.textContent).toBe('Heavy rain band · since 14:00')
    expect(document.querySelector('.map-legend__rule')?.getAttribute('title')).toBe('Pays below 50% for 3 h, with alert')
    expect(document.querySelector('.map-legend__ticks')?.textContent).toBe('40%50%70%100%+')
  })

  it('falls back to ward outlines when CARTO returns the keyless watermark', async () => {
    const digest = vi.spyOn(crypto.subtle, 'digest').mockResolvedValue(Uint8Array.from(CARTO_WATERMARK_SHA256.match(/../g) ?? [], (h) => parseInt(h, 16)).buffer)
    vi.stubGlobal('fetch', () => tileResponse(new Uint8Array([9])))
    const { getByTestId } = renderMap()
    await waitFor(() => expect(getByTestId('live-map').dataset.tiles).toBe('fallback'))
    expect(getByTestId('live-map').dataset.reason).toBe('watermark')
    expect(getByTestId('live-map').getAttribute('title')).toBe('Ward basemap (no CARTO tile key configured)')
    expect(document.querySelector('.map-offline')).toBeNull()
    expect(document.querySelector('.leaflet-control-attribution')).toBeNull()
    expect(digest).toHaveBeenCalled()
  })

  it('updates labels and hex colours in place when the snapshot changes', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('offline')))
    const view = renderMap({ merchant: null, selected: null })
    await waitFor(() => expect(view.getByTestId('live-map').dataset.tiles).toBe('fallback'))
    backend.step(60)
    const later = snapshotView(backend.runtime, backend.geo)
    view.rerender(
      <LiveMap geo={{ zones: backend.geo.zones as FeatureCollection, hexes: backend.geo.hexes as FeatureCollection }} snapshot={{ ...later, rain_band: null }} merchant={anil} selected="Z3" onSelectZone={noop} onOpenMerchant={noop} />,
    )
    expect(document.querySelector('.pin-icon')).toBeTruthy()
    expect(document.querySelector('.rain-label')).toBeNull()
  })

  it('shows a message when there is no ward geometry', () => {
    const { getByText } = renderMap({ geo: { zones: { type: 'FeatureCollection', features: [] }, hexes: { type: 'FeatureCollection', features: [] } } })
    expect(getByText('No ward geometry available')).toBeTruthy()
  })
})

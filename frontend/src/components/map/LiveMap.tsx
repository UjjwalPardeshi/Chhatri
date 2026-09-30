/**
 * Live city heat map (SPEC §20 "Live map", deck slide 6; binding decision B3): CARTO Positron
 * tiles with a no-tile fallback, ward outlines, H3 hexes coloured on the deck scale, zone labels
 * ("Z7 · 37% · 46 shops"), the rain band during alerts and the demo merchant's pin
 * ("₹1,380 paid · 17:04" once credited).
 */
import 'leaflet/dist/leaflet.css'

import type { FeatureCollection } from 'geojson'
import { useEffect, useMemo, useState } from 'react'
import { AttributionControl, MapContainer, useMap } from 'react-leaflet'

import type { MerchantDetail, StateSnapshot, ZoneSnapshot } from '../../api/types'
import { hhmm } from '../../lib/time'
import { useLatest } from '../../state/useLatest'
import { boundsOf, centroidsById, FOCUS_ZONES, type LatLng } from './geo'
import { escapeHtml, HexLayer, LabelLayer, LandLayer, MapPanes, RainBandLayer, Tiles, WardLayer, type LabelSpec, type TileFailure } from './layers'
import { Legend, MapChip, NorthArrow, OfflineNote, RainPatternDefs } from './overlays'

export const PIN_ID_PREFIX = 'merchant:'
export const WATER_ID_PREFIX = 'water:'
/** Water names shown on the deck map (fixed, non-interactive). */
export const WATER_LABELS: readonly { name: string; at: LatLng }[] = [
  { name: 'Arabian Sea', at: [18.975, 72.772] },
  { name: 'Harbour', at: [18.99, 72.945] },
]

export function waterSpecs(): LabelSpec[] {
  return WATER_LABELS.map((w) => ({
    id: `${WATER_ID_PREFIX}${w.name}`,
    at: w.at,
    html: `<span class="water-label" data-box>${escapeHtml(w.name)}</span>`,
    className: 'water-label-icon',
    movable: false,
  }))
}
const LABELLED_STATUSES: ReadonlySet<ZoneSnapshot['status']> = new Set(['triggered', 'watch', 'slow_day'])
const FIT_PADDING: [number, number] = [28, 28]
const LEAFLET_PREFIX = '<a href="https://leafletjs.com">Leaflet</a>'

export type MapGeo = { zones: FeatureCollection; hexes: FeatureCollection }

export function zoneLabelSpecs(zones: readonly ZoneSnapshot[], centroids: ReadonlyMap<string, LatLng>, always: readonly (string | null)[]): LabelSpec[] {
  return zones.flatMap((zone) => {
    const at = centroids.get(zone.zone_id)
    if (!at || !(LABELLED_STATUSES.has(zone.status) || always.includes(zone.zone_id))) return []
    const slow = zone.status === 'slow_day'
    const pct = zone.live_index_pct ?? zone.index_pct
    const body = slow
      ? `<div class="zone-label zone-label--slow" data-box><strong>${escapeHtml(zone.zone_id)} · ${pct ?? '—'}% of expected</strong><span>Slow day, no alert: no payout</span></div>`
      : `<div class="zone-label zone-label--${zone.status}" data-box>${escapeHtml(zone.label)}</div>`
    const html = `<div class="zone-anchor"><span class="zone-anchor__line"></span><span class="zone-anchor__dot"></span>${body}</div>`
    return [{ id: zone.zone_id, at, html, className: `zone-label-icon zone-label-icon--${zone.status}`, movable: true }]
  })
}

/** "₹1,380 paid · 17:04" for the latest payout credited on the scenario day. */
export function pinCaption(merchant: MerchantDetail, day: string): string {
  const credited = merchant.payouts.filter((p) => p.status === 'CREDITED' && p.credited_at?.startsWith(day))
  const latest = credited.at(-1)
  if (latest) return `${latest.amount_label} paid · ${hhmm(latest.credited_at)}`
  if (merchant.payouts.some((p) => p.status === 'PENDING')) return 'Payout on its way'
  return merchant.covered ? `Covered · ${merchant.zone_id}` : `Not covered · ${merchant.zone_id}`
}

export function pinSpec(merchant: MerchantDetail, day: string): LabelSpec {
  const caption = pinCaption(merchant, day)
  const paid = caption.includes(' paid · ')
  const html = `<div class="pin ${paid ? 'pin--paid' : ''}"><span class="pin__dot"></span><div class="pin__card" data-box><strong>${escapeHtml(merchant.shop_name)}</strong><span>${escapeHtml(caption)}</span></div></div>`
  return { id: `${PIN_ID_PREFIX}${merchant.id}`, at: [merchant.lat, merchant.lng], html, className: 'pin-icon', movable: false }
}

export function rainCaption(zones: readonly ZoneSnapshot[], band: FeatureCollection): string {
  const ids = new Set(band.features.map((f) => String(f.properties?.id ?? '')))
  const starts = zones.filter((z) => ids.has(z.zone_id) && z.alert).map((z) => hhmm(z.alert?.valid_from))
  const since = starts.toSorted()[0]
  return since ? `Heavy rain band · since ${since}` : 'Heavy rain band'
}

function ResizeWatcher() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    observer.observe(container)
    return () => observer.disconnect()
  }, [map])
  return null
}

type Props = {
  geo: MapGeo
  snapshot: StateSnapshot
  merchant: MerchantDetail | null
  selected: string | null
  onSelectZone: (zoneId: string) => void
  onOpenMerchant: (merchantId: string) => void
}

export function LiveMap({ geo, snapshot, merchant, selected, onSelectZone, onOpenMerchant }: Props) {
  const [offline, setOffline] = useState<TileFailure | null>(null)
  const bounds = useMemo(() => boundsOf(geo.zones, FOCUS_ZONES), [geo.zones])
  const centroids = useMemo(() => centroidsById(geo.zones), [geo.zones])
  const day = snapshot.clock.now.slice(0, 10)
  const labels = useMemo(() => {
    const zoneLabels = zoneLabelSpecs(snapshot.zones, centroids, [merchant?.zone_id ?? null, selected])
    const fixed = merchant ? [...waterSpecs(), pinSpec(merchant, day)] : waterSpecs()
    return [...fixed, ...zoneLabels]
  }, [snapshot.zones, centroids, merchant, selected, day])
  const handlers = useLatest({ onSelectZone, onOpenMerchant })
  const onLabel = useMemo(
    () => (id: string) => {
      if (id.startsWith(WATER_ID_PREFIX)) return
      if (id.startsWith(PIN_ID_PREFIX)) handlers.current.onOpenMerchant(id.slice(PIN_ID_PREFIX.length))
      else handlers.current.onSelectZone(id)
    },
    [handlers],
  )
  const alertActive = snapshot.zones.some((z) => z.status === 'triggered' || z.status === 'watch') || snapshot.rain_band !== null
  if (!bounds) return <div className="map-frame map-frame--empty">No ward geometry available</div>

  return (
    <div className={`map-frame ${offline ? 'map-frame--offline' : ''}`} data-testid="live-map" data-tiles={offline ? 'fallback' : 'carto'}>
      <RainPatternDefs />
      <MapContainer bounds={bounds} boundsOptions={{ padding: FIT_PADDING }} zoomControl={false} attributionControl={false} className="map" zoomSnap={0.25}>
        <AttributionControl position="bottomleft" prefix={LEAFLET_PREFIX} />
        <MapPanes />
        <ResizeWatcher />
        {offline ? <LandLayer zones={geo.zones} /> : <Tiles onFallback={setOffline} />}
        <HexLayer hexes={geo.hexes} values={snapshot.hexes} />
        <WardLayer zones={geo.zones} snapshots={snapshot.zones} selected={selected} offline={offline !== null} onSelect={onSelectZone} />
        {snapshot.rain_band ? <RainBandLayer band={snapshot.rain_band} caption={rainCaption(snapshot.zones, snapshot.rain_band)} /> : null}
        <LabelLayer labels={labels} onSelect={onLabel} />
      </MapContainer>
      <MapChip clock={snapshot.clock} alertActive={alertActive} />
      <NorthArrow />
      <Legend />
      {offline ? <OfflineNote reason={offline} /> : null}
    </div>
  )
}

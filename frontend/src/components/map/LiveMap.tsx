/**
 * Live city heat map (SPEC §20 "Live map", deck slide 6; binding decision B3): OpenStreetMap tiles,
 * softly muted, when they load, otherwise a basemap drawn from the ward polygons (land without
 * shops stippled). The heat is a wash, not a grid: H3 hexes coloured on the deck scale, blurred and
 * multiplied onto the map so its place, district and sector names stay readable (heat.tsx). The
 * rest of the Mumbai Metropolitan Region carries a fainter simulated context wash (display only,
 * labelled). Navy ward hairlines, the selected zone in navy; zone labels ("Z7 · 37% · 46 shops")
 * on leader lines; the rain band hatched above the heat with its pill on a leader above the band;
 * and the demo merchant's pin ("₹1,380 paid · 17:04" once credited, with one ring pulse).
 *
 * Views: "Mumbai" frames the storm cluster (Z3, Z7, Z12) with Z9's callout kept in view; "MMR"
 * frames the whole region. A calm desktop map opens on MMR and moves to the storm once a rain band
 * or an alert appears; phones stay on Mumbai; a choice on the switch always wins.
 */
import 'leaflet/dist/leaflet.css'

import type { FeatureCollection } from 'geojson'
import L from 'leaflet'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AttributionControl, MapContainer, useMap } from 'react-leaflet'

import type { MerchantDetail, StateSnapshot, ZoneSnapshot } from '../../api/types'
import type { TriggerRule } from '../../lib/rules'
import { hhmm } from '../../lib/time'
import { basemap } from '../../state/tileStatus'
import { useLatest } from '../../state/useLatest'
import { useMediaQuery } from '../../state/useMediaQuery'
import { localHour } from '../../lib/contextIndex'
import { contextBounds } from '../../lib/mmrCells'
import { centroidsById, northernmostOf, regionFrame, stormFrame, type Bounds, type LatLng } from './geo'
import { ContextHover, ContextLayer, HeatBlur } from './heat'
import { escapeHtml, HexLayer, LabelLayer, LandLayer, MapPanes, RainBandLayer, SelectedZoneLayer, Tiles, WardLayer, type LabelSpec, type TileFailure } from './layers'
import { alertStatus, basemapTitle, Legend, MapPatternDefs, NorthArrow, OfflineNote, StatusChip, ViewToggle, type MapView } from './overlays'

export const PIN_ID_PREFIX = 'merchant:'
export const WATER_ID_PREFIX = 'water:'
export const RAIN_LABEL_ID = 'rain-band'
/** SVG pattern ids of the live map (MapPatternDefs): `live-hatch`, `live-stipple`. */
export const LIVE_PATTERNS = 'live'
/** The rain pill sits above the band (screen angle, radians). */
const UP = -Math.PI / 2
/** Water names shown on the deck map (fixed, non-interactive). */
export const WATER_LABELS: readonly { name: string; at: LatLng }[] = [
  { name: 'Arabian Sea', at: [18.975, 72.772] },
  { name: 'Harbour', at: [18.99, 72.945] },
]
/** Phones frame only the storm cluster (deck slide 6 at 390 px); wider screens keep Z9 in view. */
export const COMPACT_QUERY = '(max-width: 600px)'
/** Room around the frame (px): the status chip sits top left, the legend bottom right. */
const FRAME_PADDING: Readonly<{ topLeft: [number, number]; bottomRight: [number, number] }> = Object.freeze({ topLeft: [56, 60], bottomRight: [56, 64] })
const COMPACT_PADDING: Readonly<{ topLeft: [number, number]; bottomRight: [number, number] }> = Object.freeze({ topLeft: [24, 36], bottomRight: [24, 56] })

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
/** Placement priority: the loss first, then the watch, then context (lower = placed earlier). */
const STATUS_PRIORITY: Readonly<Record<ZoneSnapshot['status'], number>> = Object.freeze({ triggered: 0, watch: 1, slow_day: 2, normal: 3, no_data: 4 })

export type MapGeo = { zones: FeatureCollection; hexes: FeatureCollection }

function zoneLabelHtml(zone: ZoneSnapshot, selected: boolean): string {
  const ring = selected ? ' zone-label--selected' : ''
  if (zone.status !== 'slow_day') return `<div class="zone-label zone-label--${zone.status}${ring}" data-box>${escapeHtml(zone.label)}</div>`
  /** B3: labels read the trailing 3-hour index (the explanation's 61%), never the sliding live one. */
  const pct = zone.index_pct
  return `<div class="zone-label zone-label--slow${ring}" data-box><strong>${escapeHtml(zone.zone_id)} · ${pct ?? '—'}% of expected</strong><span>Slow day, no alert: no payout</span></div>`
}

export function zoneLabelSpecs(zones: readonly ZoneSnapshot[], centroids: ReadonlyMap<string, LatLng>, always: readonly (string | null)[], selected: string | null = null): LabelSpec[] {
  const wanted = zones.filter((zone) => centroids.has(zone.zone_id) && (LABELLED_STATUSES.has(zone.status) || always.includes(zone.zone_id)))
  return wanted
    .toSorted((a, b) => STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status])
    .map((zone) => {
      const html = `<div class="zone-anchor"><span class="zone-anchor__line"></span><span class="zone-anchor__dot"></span>${zoneLabelHtml(zone, zone.zone_id === selected)}</div>`
      return { id: zone.zone_id, at: centroids.get(zone.zone_id) as LatLng, html, className: `zone-label-icon zone-label-icon--${zone.status}`, movable: true }
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

/**
 * The rain band's label (deck slide 6): a pill on a short leader from the band's northern edge,
 * placed like a zone label (preferring to sit above the band) so it is never cut by the map edge.
 */
export function rainSpec(zones: readonly ZoneSnapshot[], band: FeatureCollection): LabelSpec | null {
  const top = northernmostOf(band)
  if (!top) return null
  const icon = '<svg class="rain-pill__icon" viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M12 2.5c-.3 0-.6.2-.8.5C9.5 5.6 5.5 11 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 11 14.5 5.6 12.8 3c-.2-.3-.5-.5-.8-.5Z"/></svg>'
  const pill = `<span class="rain-pill rain-label" data-box>${icon}<span class="rain-label__text">${escapeHtml(rainCaption(zones, band))}</span></span>`
  const html = `<div class="zone-anchor zone-anchor--rain"><span class="zone-anchor__line"></span><span class="zone-anchor__dot"></span>${pill}</div>`
  return { id: RAIN_LABEL_ID, at: top, html, className: 'rain-label-icon', movable: true, prefer: UP }
}

/** Quarter zoom steps let a frame fill the map; FLY_SECONDS is the view switch's flight. */
const ZOOM_SNAP = 0.25
const FLY_SECONDS = 0.9
const SHARP_FRACTION = 0.75
const EPSILON = 1e-9

/**
 * The deepest sharp zoom at or below `zoom`. Leaflet draws the nearest tile level scaled: a whole
 * zoom at 1x and .75 at 0.84x keep the map's names crisp; .25 stretches tiles (blurred) and .5
 * shrinks them too far to read.
 */
export function crispZoom(zoom: number): number {
  const whole = Math.floor(zoom + EPSILON)
  return zoom - whole >= SHARP_FRACTION - EPSILON ? whole + SHARP_FRACTION : whole
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Fits the frame on mount and on resize; a change of view flies there (unless motion is reduced).
 * Over tiles the zoom is capped at a crisp level; the drawn basemap is vector and fills the frame.
 */
function Framer({ bounds, compact, crisp }: { bounds: Bounds; compact: boolean; crisp: boolean }) {
  const map = useMap()
  const key = JSON.stringify(bounds)
  const shown = useRef<string | null>(null)
  useEffect(() => {
    const padding = compact ? COMPACT_PADDING : FRAME_PADDING
    const frame = () => {
      const ideal = map.getBoundsZoom(bounds, false, L.point(padding.topLeft).add(padding.bottomRight))
      return { paddingTopLeft: padding.topLeft, paddingBottomRight: padding.bottomRight, ...(crisp ? { maxZoom: crispZoom(ideal) } : {}) }
    }
    const fit = () => map.fitBounds(bounds, { ...frame(), animate: false })
    let size = map.getSize()
    const moved = shown.current !== null && shown.current !== key
    if (moved && size.x > 0 && size.y > 0 && !prefersReducedMotion()) map.flyToBounds(bounds, { ...frame(), duration: FLY_SECONDS })
    else fit()
    shown.current = key
    let raf = 0
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        map.invalidateSize({ pan: false })
        const next = map.getSize()
        if (next.equals(size)) return
        size = next
        fit()
      })
    })
    observer.observe(map.getContainer())
    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
    }
  }, [map, key, compact, crisp]) // eslint-disable-line react-hooks/exhaustive-deps -- `key` stands for `bounds`
  return null
}

/** A storm is on the map once a rain band or an alert (watch or triggered) is live. */
function stormy(snapshot: StateSnapshot): boolean {
  return snapshot.rain_band !== null || snapshot.zones.some((z) => z.status === 'triggered' || z.status === 'watch')
}

/** The rain band's points that pull the simulated context down (zone centroids of the band). */
function rainPoints(band: FeatureCollection | null): LatLng[] {
  return band ? [...centroidsById(band).values()] : []
}

type Props = {
  geo: MapGeo
  snapshot: StateSnapshot
  merchant: MerchantDetail | null
  selected: string | null
  /** The published trigger rule for the legend (fs-08 13.2); null until `GET /api/policy` has answered. */
  rule?: TriggerRule | null
  onSelectZone: (zoneId: string) => void
  onOpenMerchant: (merchantId: string) => void
}

function useLabels(geo: MapGeo, snapshot: StateSnapshot, merchant: MerchantDetail | null, selected: string | null): LabelSpec[] {
  const centroids = useMemo(() => centroidsById(geo.zones), [geo.zones])
  const day = snapshot.clock.now.slice(0, 10)
  return useMemo(() => {
    const rain = snapshot.rain_band ? rainSpec(snapshot.zones, snapshot.rain_band) : null
    const fixed = [...waterSpecs(), ...(merchant ? [pinSpec(merchant, day)] : [])]
    const always = [selected, merchant?.zone_id ?? null]
    return [...fixed, ...zoneLabelSpecs(snapshot.zones, centroids, always, selected), ...(rain ? [rain] : [])]
  }, [snapshot.zones, snapshot.rain_band, centroids, merchant, selected, day])
}

export function LiveMap({ geo, snapshot, merchant, selected, rule = null, onSelectZone, onOpenMerchant }: Props) {
  const [offline, setOffline] = useState<TileFailure | null>(null)
  const [tilesShown, setTilesShown] = useState(false)
  const [choice, setChoice] = useState<MapView | null>(null)
  const compact = useMediaQuery(COMPACT_QUERY)
  const view: MapView = choice ?? (compact || stormy(snapshot) ? 'city' : 'mmr')
  const cityBounds = useMemo(() => stormFrame(geo.zones, compact), [geo.zones, compact])
  const regionBounds = useMemo(() => regionFrame(geo.zones, contextBounds()), [geo.zones])
  const bounds = view === 'mmr' ? regionBounds : cityBounds
  const labels = useLabels(geo, snapshot, merchant, selected)
  const hour = localHour(snapshot.clock.now)
  const rain = useMemo(() => rainPoints(snapshot.rain_band), [snapshot.rain_band])
  const handlers = useLatest({ onSelectZone, onOpenMerchant })
  const onLabel = useMemo(
    () => (id: string) => {
      if (id.startsWith(WATER_ID_PREFIX) || id === RAIN_LABEL_ID) return
      if (id.startsWith(PIN_ID_PREFIX)) handlers.current.onOpenMerchant(id.slice(PIN_ID_PREFIX.length))
      else handlers.current.onSelectZone(id)
    },
    [handlers],
  )
  useEffect(() => basemap.set(offline ?? (tilesShown ? 'tiles' : 'unknown')), [offline, tilesShown])
  useEffect(() => () => basemap.set('unknown'), [])
  if (!cityBounds || !bounds) return <div className="map-frame map-frame--empty">No ward geometry available</div>

  return (
    <div className={`map-frame ${offline ? 'map-frame--drawn' : ''}`} data-testid="live-map" data-tiles={offline ? 'fallback' : 'osm'} data-view={view} data-reason={offline ?? undefined} title={basemapTitle(offline)}>
      <MapPatternDefs prefix={LIVE_PATTERNS} />
      <MapContainer bounds={bounds} zoomControl={false} attributionControl={false} className="map" zoomSnap={ZOOM_SNAP}>
        {tilesShown && !offline ? <AttributionControl position="bottomleft" prefix={false} /> : null}
        <MapPanes />
        <HeatBlur />
        <Framer bounds={bounds} compact={compact} crisp={!offline} />
        {offline ? <LandLayer zones={geo.zones} patterns={LIVE_PATTERNS} /> : <Tiles onFallback={setOffline} onLoaded={() => setTilesShown(true)} />}
        <ContextLayer hour={hour} rain={rain} />
        <ContextHover hour={hour} rain={rain} />
        <HexLayer hexes={geo.hexes} values={snapshot.hexes} />
        <WardLayer zones={geo.zones} snapshots={snapshot.zones} selected={selected} onSelect={onSelectZone} />
        {snapshot.rain_band ? <RainBandLayer band={snapshot.rain_band} patterns={LIVE_PATTERNS} /> : null}
        <SelectedZoneLayer zones={geo.zones} selected={selected} />
        <LabelLayer labels={labels} onSelect={onLabel} />
      </MapContainer>
      <StatusChip status={alertStatus(snapshot.zones, snapshot.clock)} />
      <ViewToggle view={view} onChange={setChoice} />
      <NorthArrow />
      <Legend patterns={LIVE_PATTERNS} rule={rule} context />
      {offline ? <OfflineNote reason={offline} /> : null}
    </div>
  )
}

/**
 * Data layers for the live map (SPEC §20 "Live map", B3): H3 hexes on the deck colour scale, ward
 * borders as white lines over the hexes (they read as structure, not roads), the selected zone
 * outlined in navy with a white halo, and the rain band as a hatch with a dashed edge above the
 * hexes (deck slide 6). Layers are created once per GeoJSON and restyled in place, so colours
 * update smoothly with no flicker.
 *
 * Stacking: basemap < hexes < ward borders < rain band < selected zone < labels (markers).
 */
import L from 'leaflet'
import type { FeatureCollection } from 'geojson'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import type { ZoneSnapshot } from '../../api/types'
import { indexColour } from '../../lib/colour'
import { useLatest } from '../../state/useLatest'
import { zoneId } from './geo'

export { CARTO_ATTRIBUTION, LandLayer, TILE_ERROR_LIMIT, TILE_TIMEOUT_MS, Tiles, type TileFailure } from './basemap'
export { LabelLayer, relayout, type LabelSpec } from './labels'

const PANES: readonly [string, number][] = [
  ['land', 250],
  ['hexes', 410],
  ['wards', 420],
  ['rain', 425],
  ['selected', 430],
]

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c)
}

/** Creates the panes in stacking order. Runs before the layer effects. */
export function MapPanes() {
  const map = useMap()
  useEffect(() => {
    for (const [name, z] of PANES) {
      if (!map.getPane(name)) map.createPane(name).style.zIndex = String(z)
    }
  }, [map])
  return null
}

const HEX_STYLE: L.PathOptions = { color: '#ffffff', weight: 0.8, opacity: 0.85, fillOpacity: 0.84, className: 'hex-cell' }

export function HexLayer({ hexes, values }: { hexes: FeatureCollection; values: Record<string, number | null> }) {
  const map = useMap()
  const layers = useRef(new Map<string, L.Path>())
  const applied = useRef(new Map<string, string>())
  useEffect(() => {
    const byId = layers.current
    const appliedColours = applied.current
    const group = L.geoJSON(hexes, {
      pane: 'hexes',
      interactive: false,
      style: () => ({ ...HEX_STYLE, fillColor: indexColour(null) }),
      onEachFeature: (feature, layer) => byId.set(String(feature.properties?.h3), layer as L.Path),
    })
    group.addTo(map)
    return () => {
      group.remove()
      byId.clear()
      appliedColours.clear()
    }
  }, [map, hexes])
  useEffect(() => {
    for (const [h3, layer] of layers.current) {
      const colour = indexColour(values[h3] ?? null)
      if (applied.current.get(h3) === colour) continue
      layer.setStyle({ fillColor: colour })
      applied.current.set(h3, colour)
    }
  }, [values, hexes])
  return null
}

/** Ward border weight (px): a white line over the hexes. */
const WARD_WEIGHT = 1.5
/** Selected zone: a navy outline over a wider white halo (px). */
const SELECTED_WEIGHT = 3
const SELECTED_HALO_WEIGHT = 7

/** Border style per zone state; colours come from CSS classes (tokens), weights from here. */
export function wardStyle(status: ZoneSnapshot['status'] | undefined, selected: boolean): L.PathOptions {
  const base: L.PathOptions = { fill: true, fillColor: '#ffffff', fillOpacity: 0, weight: WARD_WEIGHT, className: 'ward' }
  if (selected) return { ...base, className: 'ward ward--selected' }
  if (status === 'triggered') return { ...base, className: 'ward ward--triggered' }
  if (status === 'watch') return { ...base, className: 'ward ward--watch' }
  return base
}

/** Leaflet only applies `className` on creation, so state classes are toggled on the element. */
const WARD_STATES = ['ward--triggered', 'ward--selected', 'ward--watch'] as const

function restyle(layer: L.Path, style: L.PathOptions): void {
  layer.setStyle(style)
  const el = (layer as L.Path & { getElement?: () => Element | undefined }).getElement?.()
  if (!el) return
  for (const name of WARD_STATES) el.classList.toggle(name, style.className?.split(' ').includes(name) ?? false)
}

type WardProps = { zones: FeatureCollection; snapshots: readonly ZoneSnapshot[]; selected: string | null; onSelect: (zoneId: string) => void }

export function WardLayer({ zones, snapshots, selected, onSelect }: WardProps) {
  const map = useMap()
  const layers = useRef(new Map<string, L.Path>())
  const selectRef = useLatest(onSelect)
  useEffect(() => {
    const byId = layers.current
    const group = L.geoJSON(zones, {
      pane: 'wards',
      style: () => wardStyle(undefined, false),
      onEachFeature: (feature, layer) => {
        const id = zoneId(feature)
        byId.set(id, layer as L.Path)
        layer.on('click', () => selectRef.current(id))
        /** Touch screens have no hover: a tapped tooltip would stick over the labels. */
        if (!touchOnly()) layer.bindTooltip(() => escapeHtml(String(feature.properties?.label ?? `${id} · ${feature.properties?.name ?? ''}`)), { sticky: true, className: 'ward-tooltip' })
      },
    })
    group.addTo(map)
    return () => {
      group.remove()
      byId.clear()
    }
  }, [map, zones, selectRef])
  useEffect(() => {
    const byStatus = new Map(snapshots.map((z) => [z.zone_id, z]))
    for (const [id, layer] of layers.current) {
      const snapshot = byStatus.get(id)
      restyle(layer, wardStyle(snapshot?.status, id === selected))
      if (layer.getTooltip()) layer.setTooltipContent(escapeHtml(snapshot ? `${snapshot.label} · ${snapshot.name}` : id))
    }
  }, [snapshots, selected, zones])
  return null
}

/** True on touch-only devices (no hover). */
function touchOnly(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(hover: none)').matches
}

/**
 * The selected zone (the card's zone): a white halo under a navy outline, above the hexes and the
 * rain band, so it reads on red hexes and on the hatch alike.
 */
export function SelectedZoneLayer({ zones, selected }: { zones: FeatureCollection; selected: string | null }) {
  const map = useMap()
  useEffect(() => {
    const feature = zones.features.find((f) => zoneId(f) === selected)
    if (!feature) return undefined
    const layers = [
      L.geoJSON(feature, { pane: 'selected', interactive: false, style: { className: 'zone-outline zone-outline--halo', weight: SELECTED_HALO_WEIGHT, fill: false, lineJoin: 'round' } }),
      L.geoJSON(feature, { pane: 'selected', interactive: false, style: { className: 'zone-outline', weight: SELECTED_WEIGHT, fill: false, lineJoin: 'round' } }),
    ]
    for (const layer of layers) layer.addTo(map)
    return () => {
      for (const layer of layers) layer.remove()
    }
  }, [map, zones, selected])
  return null
}

/**
 * The rain band (B3 rain_band, deck slide 6): a 45° hatch (MapPatternDefs `${patterns}-hatch`)
 * above the hexes so it reads as weather over the loss, and a dashed blue edge; it fades in when
 * the band appears (CSS).
 */
export function RainBandLayer({ band, patterns }: { band: FeatureCollection; patterns: string }) {
  const map = useMap()
  const key = JSON.stringify(band.features.map((f) => f.properties?.id ?? f.id))
  useEffect(() => {
    const layers = [
      L.geoJSON(band, { pane: 'rain', interactive: false, style: { className: 'rain-band rain-band--fill', stroke: false, fillColor: `url(#${patterns}-hatch)`, fillOpacity: 1 } }),
      L.geoJSON(band, { pane: 'rain', interactive: false, style: { className: 'rain-band rain-band--edge', weight: 2, fill: false, dashArray: '6 5', lineJoin: 'round' } }),
    ]
    for (const layer of layers) layer.addTo(map)
    return () => {
      for (const layer of layers) layer.remove()
    }
  }, [map, key, patterns]) // eslint-disable-line react-hooks/exhaustive-deps -- `key` stands for `band`
  return null
}

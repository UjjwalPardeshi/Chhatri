/**
 * Leaflet layers for the live map (SPEC §20 "Live map"). Layers are created once per GeoJSON and
 * then restyled in place, so hex colours and labels update smoothly with no flicker.
 */
import L from 'leaflet'
import type { FeatureCollection } from 'geojson'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import type { ZoneSnapshot } from '../../api/types'
import { indexColour } from '../../lib/colour'
import { probeTiles, tileTemplate, type TileProbe } from '../../lib/tiles'
import { useLatest } from '../../state/useLatest'
import { zoneId, type LatLng } from './geo'
import { layoutLabels, type LayoutItem, type Rect } from './labelLayout'

export const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a> · Wards: DataMeet (CC BY-SA 2.5 India)'
export const TILE_ERROR_LIMIT = 4
export const TILE_TIMEOUT_MS = 8_000

const PANES: readonly [string, number][] = [
  ['land', 250],
  ['hexes', 410],
  ['wards', 420],
  ['rain', 430],
]

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c)
}

/** Stacking: land < hexes < ward outlines < rain band < labels (markers). Runs before layer effects. */
export function MapPanes() {
  const map = useMap()
  useEffect(() => {
    for (const [name, z] of PANES) {
      if (!map.getPane(name)) map.createPane(name).style.zIndex = String(z)
    }
  }, [map])
  return null
}

export type TileFailure = TileProbe | 'errors'

/**
 * CARTO Positron with graceful fallback (SPEC §20): a probe tile first (watermark/offline ⇒ no
 * tiles), then repeated tile errors or no tile within the timeout ⇒ no tiles.
 */
export function Tiles({ onFallback }: { onFallback: (reason: TileFailure) => void }) {
  const map = useMap()
  const fallbackRef = useLatest(onFallback)
  useEffect(() => {
    let cancelled = false
    let layer: L.TileLayer | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    const fail = (reason: TileFailure) => {
      if (cancelled) return
      console.warn(`[map] basemap unavailable (${reason}); showing ward outlines only`)
      layer?.remove()
      fallbackRef.current(reason)
    }
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      fail('unreachable')
      return undefined
    }
    const template = tileTemplate(import.meta.env.VITE_TILE_URL)
    const centre = map.getCenter()
    void probeTiles(window.fetch.bind(window), template, centre.lat, centre.lng).then((result) => {
      if (cancelled) return
      if (result !== 'ok') {
        fail(result)
        return
      }
      let loaded = 0
      let failed = 0
      const tiles = L.tileLayer(template, { subdomains: 'abcd', maxZoom: 19, attribution: CARTO_ATTRIBUTION, className: 'map-tiles' })
      tiles.on('tileload', () => {
        loaded += 1
      })
      tiles.on('tileerror', () => {
        failed += 1
        if (loaded === 0 && failed === TILE_ERROR_LIMIT) fail('errors')
      })
      timer = setTimeout(() => {
        if (loaded === 0) fail('errors')
      }, TILE_TIMEOUT_MS)
      layer = tiles
      tiles.addTo(map)
    })
    return () => {
      cancelled = true
      clearTimeout(timer)
      layer?.remove()
    }
  }, [map, fallbackRef])
  return null
}

/** Plain land fill under the hexes when tiles are unavailable. */
export function LandLayer({ zones }: { zones: FeatureCollection }) {
  const map = useMap()
  useEffect(() => {
    const layer = L.geoJSON(zones, { pane: 'land', interactive: false, style: { color: '#c5ced9', weight: 1, opacity: 1, fillColor: '#f2f4f7', fillOpacity: 1 } })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, zones])
  return null
}

const HEX_STYLE: L.PathOptions = { color: '#ffffff', weight: 0.8, opacity: 0.85, fillOpacity: 0.8, className: 'hex-cell' }

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

function wardStyle(status: ZoneSnapshot['status'] | undefined, selected: boolean, offline: boolean): L.PathOptions {
  const base: L.PathOptions = { fill: true, fillColor: '#ffffff', fillOpacity: 0, color: '#0f1a33', weight: 0.9, opacity: offline ? 0.55 : 0.35 }
  if (status === 'triggered') return { ...base, color: '#b91c1c', weight: 2.2, opacity: 0.95 }
  if (selected) return { ...base, color: '#0b63c9', weight: 2.4, opacity: 0.95 }
  if (status === 'watch') return { ...base, color: '#a8520f', weight: 1.6, opacity: 0.8 }
  return base
}

type WardProps = { zones: FeatureCollection; snapshots: readonly ZoneSnapshot[]; selected: string | null; offline: boolean; onSelect: (zoneId: string) => void }

export function WardLayer({ zones, snapshots, selected, offline, onSelect }: WardProps) {
  const map = useMap()
  const layers = useRef(new Map<string, L.Path>())
  const selectRef = useLatest(onSelect)
  useEffect(() => {
    const byId = layers.current
    const group = L.geoJSON(zones, {
      pane: 'wards',
      onEachFeature: (feature, layer) => {
        const id = zoneId(feature)
        byId.set(id, layer as L.Path)
        layer.on('click', () => selectRef.current(id))
        layer.bindTooltip(() => escapeHtml(String(feature.properties?.label ?? `${id} · ${feature.properties?.name ?? ''}`)), { sticky: true, className: 'ward-tooltip' })
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
      layer.setStyle(wardStyle(snapshot?.status, id === selected, offline))
      layer.setTooltipContent(escapeHtml(snapshot ? `${snapshot.label} · ${snapshot.name}` : id))
    }
  }, [snapshots, selected, offline, zones])
  return null
}

export function RainBandLayer({ band, caption }: { band: FeatureCollection; caption: string }) {
  const map = useMap()
  const key = JSON.stringify(band.features.map((f) => f.properties?.id ?? f.id))
  useEffect(() => {
    const layer = L.geoJSON(band, { pane: 'rain', interactive: false, style: { className: 'rain-band', color: '#0b63c9', weight: 1.4, opacity: 0.55, dashArray: '5 5', fillOpacity: 1 } })
    layer.addTo(map)
    const bounds = layer.getBounds()
    const label = L.marker(bounds.getNorthWest(), {
      interactive: false,
      keyboard: false,
      icon: L.divIcon({ className: 'rain-label-icon', html: `<span class="rain-label">${escapeHtml(caption)}</span>`, iconSize: undefined }),
    })
    label.addTo(map)
    return () => {
      layer.remove()
      label.remove()
    }
  }, [map, key, caption]) // eslint-disable-line react-hooks/exhaustive-deps -- `key` stands for `band`
  return null
}

export type LabelSpec = { id: string; at: LatLng; html: string; className: string; movable: boolean }

type Placed = { marker: L.Marker; html: string; className: string }

function relativeRect(el: Element, container: HTMLElement): Rect {
  const r = el.getBoundingClientRect()
  const c = container.getBoundingClientRect()
  return { x: r.left - c.left, y: r.top - c.top, w: r.width, h: r.height }
}

/** Collision-free placement of movable labels around their anchors (see labelLayout.ts). */
function relayout(map: L.Map, specs: readonly LabelSpec[], markers: ReadonlyMap<string, Placed>): void {
  const container = map.getContainer()
  const items: LayoutItem[] = specs.flatMap((spec) => {
    const el = markers.get(spec.id)?.marker.getElement()
    const box = el?.querySelector<HTMLElement>('[data-box]')
    if (!el || !box) return []
    const anchor = map.latLngToContainerPoint(spec.at)
    const fixed = spec.movable ? null : relativeRect(box, container)
    return [{ id: spec.id, anchor, w: box.offsetWidth, h: box.offsetHeight, fixed }]
  })
  const size = map.getSize()
  const offsets = layoutLabels(items, { x: 0, y: 0, w: size.x, h: size.y })
  for (const [id, offset] of offsets) {
    const el = markers.get(id)?.marker.getElement()?.querySelector<HTMLElement>('.zone-anchor')
    if (!el) continue
    const length = Math.hypot(offset.dx, offset.dy)
    el.style.setProperty('--dx', `${offset.dx}px`)
    el.style.setProperty('--dy', `${offset.dy}px`)
    el.style.setProperty('--len', `${length}px`)
    el.style.setProperty('--angle', `${Math.atan2(offset.dy, offset.dx)}rad`)
    el.dataset.moved = String(length > 0)
  }
}

export function LabelLayer({ labels, onSelect }: { labels: readonly LabelSpec[]; onSelect: (id: string) => void }) {
  const map = useMap()
  const markers = useRef(new Map<string, Placed>())
  const specsRef = useLatest(labels)
  const selectRef = useLatest(onSelect)
  useEffect(() => {
    const current = markers.current
    const wanted = new Set(labels.map((l) => l.id))
    for (const [id, entry] of current) {
      if (!wanted.has(id)) {
        entry.marker.remove()
        current.delete(id)
      }
    }
    for (const spec of labels) {
      const existing = current.get(spec.id)
      const icon = L.divIcon({ className: `map-label-icon ${spec.className}`, html: spec.html, iconSize: undefined })
      if (existing && (existing.html !== spec.html || existing.className !== spec.className)) {
        existing.marker.setIcon(icon)
        current.set(spec.id, { ...existing, html: spec.html, className: spec.className })
      } else if (!existing) {
        const marker = L.marker(spec.at, { icon, keyboard: false, riseOnHover: true, zIndexOffset: spec.movable ? 0 : 1000 })
        marker.on('click', () => selectRef.current(spec.id))
        marker.addTo(map)
        current.set(spec.id, { marker, html: spec.html, className: spec.className })
      }
    }
    relayout(map, labels, current)
  }, [map, labels, selectRef])
  useEffect(() => {
    const current = markers.current
    let frame = 0
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => relayout(map, specsRef.current, current))
    }
    map.on('zoomend moveend resize', schedule)
    return () => {
      cancelAnimationFrame(frame)
      map.off('zoomend moveend resize', schedule)
      for (const entry of current.values()) entry.marker.remove()
      current.clear()
    }
  }, [map, specsRef])
  return null
}

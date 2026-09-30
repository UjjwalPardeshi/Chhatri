/**
 * Map labels as Leaflet markers (SPEC §20 "zone labels", deck slide 6): zone chips on leader
 * lines, the merchant pin, the rain pill and the water names. Fixed labels (pin, rain pill, water)
 * and the map's HTML overlays (legend, status chip, north arrow, toast; marked `data-obstacle`)
 * are obstacles; zone labels are placed around them by `layoutLabels` after every change, zoom,
 * move and resize.
 */
import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { useLatest } from '../../state/useLatest'
import type { LatLng } from './geo'
import { layoutLabels, type LayoutItem, type Rect } from './labelLayout'

/** A map label. `prefer` (radians, -π/2 = up) overrides "outward from the storm" for movable labels. */
export type LabelSpec = { id: string; at: LatLng; html: string; className: string; movable: boolean; prefer?: number }

type Placed = { marker: L.Marker; html: string; className: string }

/** Markers above zone labels: fixed labels (pin, rain pill) stay on top when boxes touch. */
const FIXED_Z_OFFSET = 1000

function relativeRect(el: Element, container: HTMLElement): Rect {
  const r = el.getBoundingClientRect()
  const c = container.getBoundingClientRect()
  return { x: r.left - c.left, y: r.top - c.top, w: r.width, h: r.height }
}

/** Boxes of the HTML overlays drawn over the map (they sit in the map frame, outside Leaflet). */
function overlayRects(container: HTMLElement): Rect[] {
  const frame = container.parentElement
  if (!frame) return []
  return [...frame.querySelectorAll('[data-obstacle]')].map((el) => relativeRect(el, container)).filter((r) => r.w > 0 && r.h > 0)
}

/** Moves a `.zone-anchor` label to its placed offset and sizes its leader line (CSS variables). */
export function applyOffset(el: HTMLElement, dx: number, dy: number): void {
  const length = Math.hypot(dx, dy)
  el.style.setProperty('--dx', `${dx}px`)
  el.style.setProperty('--dy', `${dy}px`)
  el.style.setProperty('--len', `${length}px`)
  el.style.setProperty('--angle', `${Math.atan2(dy, dx)}rad`)
  el.dataset.moved = String(length > 0)
}

/** Collision-free placement of movable labels around their anchors (see labelLayout.ts). */
export function relayout(map: L.Map, specs: readonly LabelSpec[], markers: ReadonlyMap<string, Placed>): void {
  const container = map.getContainer()
  const items: LayoutItem[] = specs.flatMap((spec) => {
    const el = markers.get(spec.id)?.marker.getElement()
    const box = el?.querySelector<HTMLElement>('[data-box]')
    if (!el || !box) return []
    const anchor = map.latLngToContainerPoint(spec.at)
    const fixed = spec.movable ? null : relativeRect(box, container)
    return [{ id: spec.id, anchor, w: box.offsetWidth, h: box.offsetHeight, fixed, prefer: spec.prefer }]
  })
  const size = map.getSize()
  const offsets = layoutLabels(items, { x: 0, y: 0, w: size.x, h: size.y }, overlayRects(container))
  for (const [id, offset] of offsets) {
    const el = markers.get(id)?.marker.getElement()?.querySelector<HTMLElement>('.zone-anchor')
    if (el) applyOffset(el, offset.dx, offset.dy)
  }
}

function syncMarkers(map: L.Map, labels: readonly LabelSpec[], current: Map<string, Placed>, onSelect: (id: string) => void): void {
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
      const marker = L.marker(spec.at, { icon, keyboard: false, riseOnHover: true, zIndexOffset: spec.movable ? 0 : FIXED_Z_OFFSET })
      marker.on('click', () => onSelect(spec.id))
      marker.addTo(map)
      current.set(spec.id, { marker, html: spec.html, className: spec.className })
    } else if (!existing.marker.getLatLng().equals(spec.at)) {
      existing.marker.setLatLng(spec.at)
    }
  }
}

export function LabelLayer({ labels, onSelect }: { labels: readonly LabelSpec[]; onSelect: (id: string) => void }) {
  const map = useMap()
  const markers = useRef(new Map<string, Placed>())
  const specsRef = useLatest(labels)
  const selectRef = useLatest(onSelect)
  useEffect(() => {
    syncMarkers(map, labels, markers.current, (id) => selectRef.current(id))
    relayout(map, labels, markers.current)
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

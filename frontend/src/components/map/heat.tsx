/**
 * The heat as a wash, not a grid (3 Oct): cells are drawn without strokes into the `context` and
 * `hexes` panes, which the stylesheet blurs and multiplies onto the OpenStreetMap tiles, so place,
 * district and sector names stay readable through the colour. The blur follows the zoom (about half
 * a cell), so neighbouring cells always melt into one surface.
 *
 * The rest of the Mumbai Metropolitan Region (mmrCells.ts) is simulated context: a fainter wash,
 * labelled on hover and in the legend, never a KPI, a trigger or a payout.
 */
import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { indexColour, NO_DATA_COLOUR } from '../../lib/colour'
import { contextIndex } from '../../lib/contextIndex'
import { cellAt, cellRing, contextCells, type LatLngTuple } from '../../lib/mmrCells'
import { useLatest } from '../../state/useLatest'
import { escapeHtml, touchOnly } from './layers'

/** About the width of a covered H3 cell (resolution 8) and of a context cell (m). */
const CELL_METRES = 900
const BLUR_SHARE = 0.5
const BLUR_MIN_PX = 3
const BLUR_MAX_PX = 22
const EARTH_CIRCUMFERENCE_M = 40_075_016.686
const TILE_PX_LOG2 = 8

/** Blur radius (px) for a zoom: half a cell on screen, within [3, 22]. */
export function heatBlurPx(zoom: number, lat: number): number {
  const metresPerPx = (EARTH_CIRCUMFERENCE_M * Math.cos((lat * Math.PI) / 180)) / 2 ** (zoom + TILE_PX_LOG2)
  const px = (CELL_METRES / metresPerPx) * BLUR_SHARE
  return Math.round(Math.min(BLUR_MAX_PX, Math.max(BLUR_MIN_PX, px)) * 10) / 10
}

/** Keeps `--heat-blur` on the map container at half a cell for the current zoom. */
export function HeatBlur() {
  const map = useMap()
  useEffect(() => {
    const apply = () => map.getContainer().style.setProperty('--heat-blur', `${heatBlurPx(map.getZoom(), map.getCenter().lat)}px`)
    map.whenReady(apply)
    map.on('zoomend', apply)
    return () => {
      map.off('zoomend', apply)
    }
  }, [map])
  return null
}

const CONTEXT_STYLE: L.PolylineOptions = { pane: 'context', interactive: false, stroke: false, fillOpacity: 1, fillColor: NO_DATA_COLOUR, className: 'context-cell' }

type ContextProps = { hour: number; rain: readonly LatLngTuple[] }

/** The MMR context cells, created once and recoloured in place when the hour or the rain band moves. */
export function ContextLayer({ hour, rain }: ContextProps) {
  const map = useMap()
  const layers = useRef<L.Polygon[]>([])
  const applied = useRef<string[]>([])
  useEffect(() => {
    const polygons = contextCells().map((cell) => L.polygon(cellRing(cell), CONTEXT_STYLE))
    const group = L.layerGroup(polygons).addTo(map)
    layers.current = polygons
    applied.current = polygons.map(() => NO_DATA_COLOUR)
    return () => {
      group.remove()
      layers.current = []
      applied.current = []
    }
  }, [map])
  const rainKey = JSON.stringify(rain)
  useEffect(() => {
    const cells = contextCells()
    layers.current.forEach((layer, i) => {
      const colour = indexColour(contextIndex(cells[i], hour, rain))
      if (applied.current[i] === colour) return
      layer.setStyle({ fillColor: colour })
      applied.current[i] = colour
    })
  }, [hour, rainKey]) // eslint-disable-line react-hooks/exhaustive-deps -- `rainKey` stands for `rain`
  return null
}

/** "Thane · 94% of expected" with the simulated note, for the cell under the pointer. */
export function contextTooltipHtml(region: string, pct: number): string {
  return `<strong>${escapeHtml(region)} · ${pct}% of expected</strong><br><span class="context-tooltip__note">Simulated context · not covered, no payout</span>`
}

/** Hover read-out for the context wash (pointer devices only; the cells themselves are not interactive). */
export function ContextHover({ hour, rain }: ContextProps) {
  const map = useMap()
  const latest = useLatest({ hour, rain })
  useEffect(() => {
    if (touchOnly()) return undefined
    const tooltip = L.tooltip({ className: 'ward-tooltip context-tooltip', direction: 'top', offset: [0, -10], opacity: 1 })
    let shown: number | null = null
    const hide = () => {
      if (shown === null) return
      map.closeTooltip(tooltip)
      shown = null
    }
    const move = (event: L.LeafletMouseEvent) => {
      const cell = cellAt(event.latlng.lat, event.latlng.lng)
      if (!cell) return hide()
      if (shown !== cell.id) tooltip.setContent(contextTooltipHtml(cell.region, contextIndex(cell, latest.current.hour, latest.current.rain)))
      tooltip.setLatLng(event.latlng)
      if (shown === null) map.openTooltip(tooltip)
      shown = cell.id
    }
    map.on('mousemove', move)
    map.on('mouseout', hide)
    return () => {
      map.off('mousemove', move)
      map.off('mouseout', hide)
      hide()
    }
  }, [map, latest])
  return null
}

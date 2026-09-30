/** Map framing and label placement (SPEC §20 "Live map", deck slide 6). */
import type { FeatureCollection } from 'geojson'
import { describe, expect, it } from 'vitest'

import { testBackend } from '../../mock/testkit'
import { boundsOf, centroidsById, extendBounds, northernmostOf, stormFrame, STORM_ZONES } from './geo'
import { candidateOffsets, clampOffset, EDGE_INSET, layoutLabels, LEADER_STEPS, overlapArea, type LayoutItem, type Rect } from './labelLayout'

const BOUNDS: Rect = { x: 0, y: 0, w: 400, h: 300 }

function item(id: string, x: number, y: number, fixed: Rect | null = null): LayoutItem {
  return { id, anchor: { x, y }, w: 80, h: 20, fixed }
}

function boxOf(target: LayoutItem, offset: { dx: number; dy: number }): Rect {
  return { x: target.anchor.x + offset.dx - target.w / 2, y: target.anchor.y + offset.dy - target.h / 2, w: target.w, h: target.h }
}

describe('label layout', () => {
  it('tries the outward direction first, shortest leader first', () => {
    const [first] = candidateOffsets(item('a', 300, 150), { x: 200, y: 150 })
    expect(first).toEqual({ dx: 40 + LEADER_STEPS[0], dy: 0 })
    const [up] = candidateOffsets(item('b', 200, 150), null)
    expect(Math.abs(up.dx)).toBe(0)
    expect(up.dy).toBeLessThan(0)
    expect(candidateOffsets(item('c', 0, 0), null)).toHaveLength(12 * LEADER_STEPS.length)
  })

  it('clamps a box inside the map with the edge inset', () => {
    const edge = item('e', 390, 5)
    const clamped = boxOf(edge, clampOffset(edge, { dx: 0, dy: 0 }, BOUNDS))
    expect(clamped.x + clamped.w).toBe(BOUNDS.w - EDGE_INSET)
    expect(clamped.y).toBe(EDGE_INSET)
  })

  it('keeps labels off each other, off fixed labels and off overlay obstacles', () => {
    const legend: Rect = { x: 0, y: 220, w: 200, h: 80 }
    const pin = item('pin', 200, 150, { x: 180, y: 140, w: 40, h: 20 })
    const items = [pin, item('a', 190, 160), item('b', 210, 160), item('c', 100, 230)]
    const placed = layoutLabels(items, BOUNDS, [legend])
    expect(placed.has('pin')).toBe(false)
    const boxes = items.filter((i) => !i.fixed).map((i) => boxOf(i, placed.get(i.id) ?? { dx: 0, dy: 0 }))
    for (const [i, box] of boxes.entries()) {
      expect(overlapArea(box, legend)).toBe(0)
      expect(overlapArea(box, pin.fixed as Rect)).toBe(0)
      for (const other of boxes.slice(i + 1)) expect(overlapArea(box, other)).toBe(0)
      expect(box.x).toBeGreaterThanOrEqual(EDGE_INSET)
      expect(box.y + box.h).toBeLessThanOrEqual(BOUNDS.h - EDGE_INSET)
    }
  })
})

describe('storm frame', () => {
  const backend = testBackend()
  const zones = backend.geo.zones as FeatureCollection
  backend.dispose()

  it('frames the storm zones, adding the Z9 anchor except on a phone', () => {
    const storm = boundsOf(zones, STORM_ZONES)
    expect(stormFrame(zones, true)).toEqual(storm)
    const wide = stormFrame(zones, false)
    const z9 = centroidsById(zones).get('Z9')
    expect(wide && z9).toBeTruthy()
    if (!wide || !z9) return
    expect(z9[0]).toBeGreaterThanOrEqual(wide[0][0])
    expect(z9[0]).toBeLessThanOrEqual(wide[1][0])
    expect(z9[1]).toBeLessThanOrEqual(wide[1][1])
  })

  it('extends bounds to points and finds the northernmost vertex', () => {
    expect(
      extendBounds(
        [
          [19, 72.8],
          [19.1, 72.9],
        ],
        [[19.2, 72.7]],
      ),
    ).toEqual([
      [19, 72.7],
      [19.2, 72.9],
    ])
    const square: FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [72.8, 19],
                [72.9, 19],
                [72.85, 19.3],
                [72.8, 19],
              ],
            ],
          },
        },
      ],
    }
    expect(northernmostOf(square)).toEqual([19.3, 72.85])
    expect(northernmostOf({ type: 'FeatureCollection', features: [] })).toBeNull()
  })
})

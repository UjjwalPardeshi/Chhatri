import { describe, expect, it } from 'vitest'

import { CONTEXT_FLOOR_PCT, contextIndex, localHour, nearestKm } from './contextIndex'
import { cellAt, cellRing, contextBounds, contextCells, CONTEXT_SOURCE } from './mmrCells'

describe('MMR context cells', () => {
  it('decodes every cell of the lattice, each found again under its own centre', () => {
    const cells = contextCells()
    expect(cells).toHaveLength(CONTEXT_SOURCE.cells)
    for (const cell of [cells[0], cells[Math.floor(cells.length / 2)], cells[cells.length - 1]]) {
      expect(cellAt(cell.lat, cell.lng)?.id).toBe(cell.id)
      expect(cellRing(cell)).toHaveLength(6)
    }
  })

  it('finds nothing over the open sea and frames the whole region', () => {
    expect(cellAt(18.9, 72.6)).toBeNull()
    const [[south, west], [north, east]] = contextBounds()
    expect(south).toBeLessThan(19)
    expect(north).toBeGreaterThan(19.4)
    expect(west).toBeLessThan(72.9)
    expect(east).toBeGreaterThan(73.1)
  })
})

describe('contextIndex (simulated, display only)', () => {
  const cell = contextCells()[100]

  it('is stable for a cell and an hour, and drifts with the hour', () => {
    expect(contextIndex(cell, 15, [])).toBe(contextIndex(cell, 15, []))
    const day = Array.from({ length: 24 }, (_, hour) => contextIndex(cell, hour, []))
    expect(new Set(day).size).toBeGreaterThan(1)
    for (const pct of day) expect(pct).toBeGreaterThanOrEqual(82)
  })

  it('dips near the rain band but never below the floor, and ignores rain beyond its reach', () => {
    const calm = contextIndex(cell, 17, [])
    const under = contextIndex(cell, 17, [[cell.lat, cell.lng]])
    expect(under).toBeLessThan(calm)
    expect(under).toBeGreaterThanOrEqual(CONTEXT_FLOOR_PCT)
    expect(contextIndex(cell, 17, [[cell.lat + 1, cell.lng]])).toBe(calm)
  })

  it('measures km to the nearest rain point and reads the local hour', () => {
    expect(nearestKm(cell, [])).toBeNull()
    expect(nearestKm({ lat: 19, lng: 73 }, [[19.1, 73]])).toBeCloseTo(11.1, 1)
    expect(localHour('2026-07-14T16:40:00+05:30')).toBe(16)
    expect(localHour('bad')).toBe(0)
  })
})

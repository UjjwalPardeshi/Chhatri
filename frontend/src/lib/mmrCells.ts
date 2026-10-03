/**
 * The land-only hex lattice of the Mumbai Metropolitan Region outside the 24 covered BMC zones
 * (`content/mmrContext.json`, generated once by frontend/scripts/build_mmr_context.py from
 * OpenStreetMap data, ODbL). Display-only geometry: the value on these cells is simulated
 * (contextIndex.ts) and never reaches a KPI, a trigger or a payout.
 *
 * The file stores runs of columns per row of a pointy-top lattice in Web Mercator metres; this
 * module rebuilds centres and vertices, and finds the cell under a map point.
 */
import mmrContext from '../content/mmrContext.json'

export type LatLngTuple = [number, number]
export type ContextCell = {
  /** Stable index into `contextCells()` (also the order of every value array). */
  id: number
  col: number
  row: number
  lat: number
  lng: number
  /** Place name for the tooltip ("Thane", "Navi Mumbai", "Vasai area"). */
  region: string
}

type Lattice = { x0: number; y0: number; radius: number }
type MmrFile = { meta: { cells: number }; lattice: Lattice; regions: string[]; rows: [number, number[]][] }

const FILE = mmrContext as unknown as MmrFile
const EARTH_RADIUS_M = 6_378_137
const ROW_KEY = 4096
const SQRT3 = Math.sqrt(3)
const HEX_CORNERS = [0, 1, 2, 3, 4, 5]
const DEG = 180 / Math.PI
const HALF = 0.5
const ROW_STEP = 1.5

function toLatLng(x: number, y: number): LatLngTuple {
  return [(2 * Math.atan(Math.exp(y / EARTH_RADIUS_M)) - Math.PI / 2) * DEG, (x / EARTH_RADIUS_M) * DEG]
}

function toMercator(lat: number, lng: number): [number, number] {
  return [(lng / DEG) * EARTH_RADIUS_M, EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + lat / DEG / 2))]
}

function centreMetres(col: number, row: number): [number, number] {
  const { x0, y0, radius } = FILE.lattice
  const width = SQRT3 * radius
  return [x0 + col * width + (row % 2 === 0 ? 0 : width * HALF), y0 + row * ROW_STEP * radius]
}

let decoded: readonly ContextCell[] | null = null
let byKey: ReadonlyMap<number, ContextCell> | null = null

function decode(): readonly ContextCell[] {
  const cells: ContextCell[] = []
  for (const [row, runs] of FILE.rows) {
    for (let i = 0; i < runs.length; i += 3) {
      const [start, length, region] = [runs[i], runs[i + 1], runs[i + 2]]
      for (let col = start; col < start + length; col++) {
        const [lat, lng] = toLatLng(...centreMetres(col, row))
        cells.push({ id: cells.length, col, row, lat, lng, region: FILE.regions[region] ?? 'MMR' })
      }
    }
  }
  return cells
}

/** Every context cell, decoded once (about 3,000). */
export function contextCells(): readonly ContextCell[] {
  decoded ??= decode()
  return decoded
}

function cellIndex(): ReadonlyMap<number, ContextCell> {
  byKey ??= new Map(contextCells().map((cell) => [cell.row * ROW_KEY + cell.col, cell]))
  return byKey
}

/** The six vertices of a cell as [lat, lng] (pointy-top hexagon, regular in Web Mercator). */
export function cellRing(cell: Pick<ContextCell, 'col' | 'row'>): LatLngTuple[] {
  const [cx, cy] = centreMetres(cell.col, cell.row)
  const radius = FILE.lattice.radius
  return HEX_CORNERS.map((k) => {
    const angle = ((60 * k - 30) * Math.PI) / 180
    return toLatLng(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle))
  })
}

/** The context cell under a point, or null over sea, creeks or the covered zones. */
export function cellAt(lat: number, lng: number): ContextCell | null {
  const { x0, y0, radius } = FILE.lattice
  const width = SQRT3 * radius
  const [x, y] = toMercator(lat, lng)
  const rowGuess = Math.round((y - y0) / (ROW_STEP * radius))
  let best: ContextCell | null = null
  let bestDistance = Infinity
  for (let row = rowGuess - 1; row <= rowGuess + 1; row++) {
    const col = Math.round((x - x0 - (row % 2 === 0 ? 0 : width * HALF)) / width)
    const [cx, cy] = centreMetres(col, row)
    const distance = Math.hypot(x - cx, y - cy)
    if (distance < bestDistance) {
      bestDistance = distance
      best = cellIndex().get(row * ROW_KEY + col) ?? null
      if (best === null) bestDistance = distance
    }
  }
  return best !== null && bestDistance <= radius ? best : null
}

/** South-west and north-east corners of all context cells, for framing the whole region. */
export function contextBounds(): [LatLngTuple, LatLngTuple] {
  let south = Infinity
  let west = Infinity
  let north = -Infinity
  let east = -Infinity
  for (const cell of contextCells()) {
    south = Math.min(south, cell.lat)
    north = Math.max(north, cell.lat)
    west = Math.min(west, cell.lng)
    east = Math.max(east, cell.lng)
  }
  return [[south, west], [north, east]]
}

/** Where the geometry comes from, for the legend tooltip and the docs. */
export const CONTEXT_SOURCE = Object.freeze({ licence: 'ODbL 1.0', credit: 'OpenStreetMap contributors', cells: FILE.meta.cells })

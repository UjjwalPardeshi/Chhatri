/** Map legend, zone and rain labels, storm label offsets (SPEC §20 "Live map", deck slide 6). */
import type { FeatureCollection } from 'geojson'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { testBackend } from '../../mock/testkit'
import { snapshotView } from '../../mock/views'
import { deckOffset, FOCUS_ZONE, LABEL_OFFSETS, LABEL_PREFER, STORM_MAP } from '../storm/StormMap'
import { placeStormLabels } from '../storm/useStormLabels'
import { centroidsById } from './geo'
import { rainSpec, zoneLabelSpecs } from './LiveMap'
import { Legend, legendPct, MapPatternDefs } from './overlays'

describe('legend', () => {
  it('marks the 50% payout floor on the ramp', () => {
    expect(legendPct(40)).toBe(0)
    expect(legendPct(100)).toBe(100)
    expect(legendPct(130)).toBe(100)
    expect(legendPct(70)).toBe(50)
    const { container } = render(
      <>
        <MapPatternDefs prefix="t" />
        <Legend patterns="t" rule={{ floorPct: 50, hours: 3 }} />
      </>,
    )
    expect(container.querySelector('#t-hatch')).toBeTruthy()
    expect(container.querySelector('#t-stipple')).toBeTruthy()
    expect(container.querySelector('.map-legend__tick--floor')?.textContent).toBe('50%')
    expect(container.querySelector('.map-legend__keys')?.textContent).toBe('Heavy rainNo shops')
  })

  it('words the rule and places the floor from the published trigger rule (fs-08 13.2)', () => {
    const { container } = render(<Legend patterns="t" rule={{ floorPct: 45, hours: 4 }} />)
    expect(container.querySelector('.map-legend__rule')?.getAttribute('title')).toBe('Pays below 45% for 4 h, with alert')
    expect(container.querySelector('.map-legend__rule')?.textContent).toBe('Pays below 45% for 4 h, with alert')
    expect(container.querySelector('.map-legend__tick--floor')?.textContent).toBe('45%')
    expect((container.querySelector('.map-legend__floor') as HTMLElement).style.left).toBe(`${legendPct(45)}%`)
  })

  it('draws the ramp and no rule while the rules are unknown, rather than guessing a floor', () => {
    const { container } = render(<Legend patterns="t" rule={null} />)
    expect(container.querySelector('.map-legend__rule')).toBeNull()
    expect(container.querySelector('.map-legend__floor')).toBeNull()
    expect(container.querySelector('.map-legend__tick--floor')).toBeNull()
    expect(container.querySelector('.map-legend__ticks')?.textContent).toBe('40%70%100%+')
  })
})

describe('live map labels', () => {
  it('rings the selected zone’s chip and puts the rain pill on a leader above the band', () => {
    const backend = testBackend()
    backend.seek('17:05')
    const snapshot = snapshotView(backend.runtime, backend.geo)
    const centroids = centroidsById(backend.geo.zones as FeatureCollection)
    const specs = zoneLabelSpecs(snapshot.zones, centroids, [], 'Z7')
    expect(specs.find((s) => s.id === 'Z7')?.html).toContain('zone-label--selected')
    expect(specs.find((s) => s.id === 'Z3')?.html).not.toContain('zone-label--selected')
    const rain = snapshot.rain_band ? rainSpec(snapshot.zones, snapshot.rain_band) : null
    expect(rain?.movable).toBe(true)
    expect(rain?.prefer).toBeCloseTo(-Math.PI / 2)
    expect(rain?.html).toContain('zone-anchor--rain')
    backend.dispose()
  })
})

describe('storm map labels', () => {
  it('starts from the deck offsets and prefers their directions', () => {
    const z7 = STORM_MAP.labels.find((l) => l.id === FOCUS_ZONE)
    expect(z7).toBeTruthy()
    if (!z7) return
    const style = deckOffset(z7, STORM_MAP) as Record<string, string>
    expect(style['--dx']).toBe(`${(LABEL_OFFSETS.Z7[0] / STORM_MAP.w) * 100}cqw`)
    expect(LABEL_PREFER.Z3).toBeCloseTo(Math.atan2(LABEL_OFFSETS.Z3[1], LABEL_OFFSETS.Z3[0]))
  })

  it('does nothing before the figure has a size', () => {
    const figure = document.createElement('figure')
    figure.innerHTML = '<div class="zone-anchor" data-label="Z7" style="--dx: 1px"><div data-box></div></div>'
    placeStormLabels(figure, LABEL_PREFER)
    expect((figure.firstElementChild as HTMLElement).style.getPropertyValue('--dx')).toBe('1px')
  })
})

// @vitest-environment node
/**
 * Contrast of the console's text and control colours (fs-08 §13.2, design system §2.1 to §2.4, WCAG 2.2 AA). The
 * ratios are computed from tokens.css for a closed list of text and background pairs, so a token that changes
 * has to keep them (and the design-system tables) true. Text needs 4.5:1, the edge of a control or an icon 3:1.
 * Two source guards keep the pairs honest in the stylesheets: no text in `--faint`, and no rule whose own text
 * and background tokens fall under 4.5:1.
 */
import { describe, expect, it } from 'vitest'

import { consoleSheets, readTokens } from './test/cssSource'

const TEXT_MIN = 4.5
const CONTROL_MIN = 3
const WHITE = '#ffffff'

const tokens = readTokens()

/** A token name, or a literal colour, as #rrggbb (var() chains such as --paid: var(--green) are followed). */
function colourOf(reference: string): string {
  const value = reference.startsWith('#') ? reference : (tokens.get(reference) ?? '')
  const chained = /^var\(--([a-z0-9-]+)\)$/.exec(value)
  if (chained) return colourOf(chained[1])
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value)
  if (!hex) throw new Error(`colourOf: ${reference} is not a plain colour (${value || 'missing'})`)
  const digits = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join('') : hex[1]
  return `#${digits.toLowerCase()}`
}

function channel(byte: number): number {
  const s = byte / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

/** WCAG 2.x relative luminance. */
function luminance(hex: string): number {
  const n = Number.parseInt(hex.slice(1), 16)
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255)
}

function contrast(foreground: string, background: string): number {
  const [a, b] = [luminance(colourOf(foreground)), luminance(colourOf(background))]
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** [text, background, the ratio the design system documents]; every pair also has to reach 4.5. */
type Pair = readonly [text: string, background: string, documented: number]

const TEXT_ON_SURFACES: readonly Pair[] = [
  ['ink', 'card', 17.85],
  ['ink', 'paper', 16.35],
  ['ink-2', 'card', 10.35],
  ['ink-3', 'card', 7.58],
  ['ink-3', 'grey-soft', 6.57],
  ['muted', 'card', 5.97],
  ['muted', 'paper', 5.46],
  ['muted', 'paper-2', 5.27],
  ['muted', 'grey-soft', 5.18],
  ['blue', 'card', 5.77],
  ['blue', 'blue-soft', 5.01],
  ['red', 'card', 6.47],
  ['green-ink', 'card', 7.13],
  ['amber-ink', 'card', 5.41],
  ['ink', 'bubble-out', 16.1],
]

/** Design system 2.3, one row per state: white on the solid fill, then the ink on the soft tint. */
const STATUS_STATES: readonly { state: string; solid: string; solidRatio: number; tint: string; ink: string; inkRatio: number }[] = [
  { state: 'paid', solid: 'paid', solidRatio: 5.02, tint: 'paid-soft', ink: 'green-ink', inkRatio: 6.25 },
  { state: 'decided', solid: 'decided', solidRatio: 5.77, tint: 'blue-soft', ink: 'blue', inkRatio: 5.01 },
  { state: 'referred', solid: 'referred', solidRatio: 5.02, tint: 'referred-soft', ink: 'referred-ink', inkRatio: 4.79 },
  { state: 'blocked', solid: 'blocked', solidRatio: 6.47, tint: 'blocked-soft', ink: 'red', inkRatio: 5.56 },
  { state: 'live', solid: 'live', solidRatio: 5.02, tint: 'live-soft', ink: 'green-ink', inkRatio: 6.25 },
  { state: 'demo (SIMULATED)', solid: 'demo', solidRatio: 7.58, tint: 'demo-soft', ink: 'demo', inkRatio: 6.57 },
  { state: 'fallback', solid: 'fallback', solidRatio: 5.18, tint: 'fallback-soft', ink: 'fallback', inkRatio: 4.68 },
]

const ON_FILLS: readonly Pair[] = [
  [WHITE, 'blue', 5.77],
  [WHITE, 'blue-hover', 7.11],
  [WHITE, 'red', 6.47],
  [WHITE, 'green', 5.02],
  [WHITE, 'amber-solid', 5.02],
  [WHITE, 'navy', 17.27],
  [WHITE, 'wa-header', 12.2],
  ['red', 'red-soft', 5.56],
  ['amber-ink', 'amber-soft', 4.79],
  ['green-ink', 'green-soft', 6.25],
]

const ON_NAVY: readonly Pair[] = [
  ['on-navy', 'navy', 17.27],
  ['on-navy', 'navy-3', 13.42], // the pressed "Present" button (design system 8.2); computed, not in the tables
  ['on-navy-2', 'navy', 11.48],
  ['on-navy-3', 'navy', 6.88],
  ['on-navy-3', 'navy-3', 5.35],
  ['fallback-on-navy', 'navy', 7.63],
  ['fallback-on-navy', 'navy-3', 5.93],
]

/** The edge of a field, a switch or a focus ring: WCAG 1.4.11, 3:1 against what it sits on. */
const CONTROL_EDGES: readonly Pair[] = [
  ['field-border', 'card', 4.33],
  ['field-border', 'paper', 3.96],
  ['field-border', 'paper-2', 3.82],
  ['accent', 'navy', 6.23],
  ['faint', 'card', 3.1],
]

const label = ([text, background]: Pair) => `${text} on ${background}`
/** `var(--x)` as the token name `x`; null for anything else (a literal colour, a calc, a gradient). */
const single = (value: string | undefined) => (value && /^var\(--[a-z0-9-]+\)$/.test(value) ? value.slice(6, -1) : null)

describe('text pairs reach 4.5:1 (WCAG 2.2 AA)', () => {
  const pairs = [...TEXT_ON_SURFACES, ...ON_FILLS, ...ON_NAVY]
  it.each(pairs.map((pair) => [label(pair), pair] as const))('%s', (_name, pair) => {
    const ratio = contrast(pair[0], pair[1])
    expect(ratio).toBeGreaterThanOrEqual(TEXT_MIN)
    expect(ratio).toBeCloseTo(pair[2], 1)
  })
})

describe('status colours (design system 2.3): solid fills, soft tints and their ink', () => {
  it.each(STATUS_STATES.map((s) => [s.state, s] as const))('%s: white on the fill, ink on the tint', (_state, s) => {
    expect(contrast(WHITE, s.solid)).toBeGreaterThanOrEqual(TEXT_MIN)
    expect(contrast(WHITE, s.solid)).toBeCloseTo(s.solidRatio, 1)
    expect(contrast(s.ink, s.tint)).toBeGreaterThanOrEqual(TEXT_MIN)
    expect(contrast(s.ink, s.tint)).toBeCloseTo(s.inkRatio, 1)
  })

  it('keeps the green fill (--green) off its own tint as text: 4.40:1 fails, --green-ink passes', () => {
    expect(contrast('green', 'green-soft')).toBeLessThan(TEXT_MIN)
    expect(contrast('green-ink', 'green-soft')).toBeGreaterThanOrEqual(TEXT_MIN)
  })
})

describe('control edges and icons reach 3:1 (WCAG 1.4.11)', () => {
  it.each(CONTROL_EDGES.map((pair) => [label(pair), pair] as const))('%s', (_name, pair) => {
    expect(contrast(pair[0], pair[1])).toBeGreaterThanOrEqual(CONTROL_MIN)
    expect(contrast(pair[0], pair[1])).toBeCloseTo(pair[2], 1)
  })

  it('shows why --faint is for lines and icons only: it fails as text', () => {
    expect(contrast('faint', 'card')).toBeLessThan(TEXT_MIN)
    expect(contrast('faint', 'paper')).toBeLessThan(CONTROL_MIN)
  })
})

describe('the stylesheets keep the pairs', () => {
  it('sets no text in --faint (lines, borders and icons only)', () => {
    const offenders = consoleSheets().flatMap(({ name, blocks }) =>
      blocks.flatMap((block) => block.declarations.filter((d) => d.property === 'color' && d.value.includes('var(--faint)')).map(() => `${name} ${block.selector}`)),
    )
    expect(offenders).toEqual([])
  })

  it('keeps 4.5:1 in every rule that sets both its text colour and its background from tokens', () => {
    const failing = consoleSheets().flatMap(({ name, blocks }) =>
      blocks.flatMap((block) => {
        const value = (property: string) => block.declarations.findLast((d) => d.property === property)?.value
        const text = single(value('color'))
        const background = single(value('background')) ?? single(value('background-color'))
        if (!text || !background || !tokens.has(text) || !tokens.has(background)) return []
        const ratio = contrast(text, background)
        return ratio < TEXT_MIN ? [`${name} ${block.selector}: ${text} on ${background} is ${ratio.toFixed(2)}:1`] : []
      }),
    )
    expect(failing).toEqual([])
  })
})

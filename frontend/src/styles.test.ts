// @vitest-environment node
/**
 * Console type rules (fs-08 §13.1, design system §2.5 and §8.2). Presenter mode steps every `--fs-*` token one
 * rung up, so console CSS has to size text with the tokens: a raw pixel size would stay small on the projector.
 * Nothing on a console page is below `--fs-2xs`, and every animation stops under reduced motion (design system
 * §6.3). The guards read the stylesheets the browser gets.
 */
import { describe, expect, it } from 'vitest'

import { consoleSheets, readTokens, sheet, type Block } from './test/cssSource'

/** Decorative artwork the type step must not touch: the "paytm" mark drawn on the simulated Soundbox device. */
const RAW_SIZE_ALLOW: readonly { file: string; selector: string }[] = [{ file: 'merchant-panel.css', selector: '.soundbox-device__brand' }]

const TOKEN_ORDER = ['2xs', 'xs', 'sm', 'base', 'md', 'lg', 'xl', '2xl', '3xl', '4xl'] as const
const FLOOR_PX = 11
const PRESENTER_ROOTS = ['.app-header', '.control-bar', '.app-footer', '.home', '.claims', '.page']

const tokens = readTokens()
const px = (name: string): number => Number.parseFloat(tokens.get(`fs-${name}`) ?? 'NaN')

type Size = { file: string; selector: string; value: string }

function fontSizes(): Size[] {
  return consoleSheets().flatMap(({ name, blocks }) =>
    blocks.flatMap((block) => block.declarations.filter((d) => d.property === 'font-size').map((d) => ({ file: name, selector: block.selector, value: d.value }))),
  )
}

const sizeOf = (file: string, selector: string) => sheet(file).blocks.filter((b) => b.selector === selector).flatMap((b) => b.declarations.filter((d) => d.property === 'font-size').map((d) => d.value))
const describeSize = (size: Size) => `${size.file} ${size.selector} { font-size: ${size.value} }`
const allowed = (size: Size) => RAW_SIZE_ALLOW.some((entry) => entry.file === size.file && entry.selector === size.selector)

describe('console font sizes use the scale tokens', () => {
  it('has no raw font-size outside the allow-list', () => {
    const raw = fontSizes().filter((size) => !size.value.includes('var(--fs-') && !allowed(size))
    expect(raw.map(describeSize)).toEqual([])
  })

  it('has no font shorthand that carries a size', () => {
    const shorthand = consoleSheets().flatMap(({ name, blocks }) =>
      blocks.flatMap((block) => block.declarations.filter((d) => d.property === 'font' && d.value !== 'inherit').map((d) => `${name} ${block.selector} { font: ${d.value} }`)),
    )
    expect(shorthand).toEqual([])
  })

  it('keeps the allow-list to the files and selectors that still exist', () => {
    for (const entry of RAW_SIZE_ALLOW) expect(sheet(entry.file).blocks.some((b) => b.selector === entry.selector)).toBe(true)
  })

  it('puts nothing below --fs-2xs (11 px) on a console page', () => {
    expect(px('2xs')).toBe(FLOOR_PX)
    for (const name of TOKEN_ORDER) expect(px(name)).toBeGreaterThanOrEqual(FLOOR_PX)
    const rawPx = fontSizes()
      .filter((size) => !allowed(size) && /^[\d.]+px$/.test(size.value))
      .filter((size) => Number.parseFloat(size.value) < FLOOR_PX)
    expect(rawPx.map(describeSize)).toEqual([])
  })

  it('keeps the scale ascending, so a step up is always a larger size', () => {
    const sizes = TOKEN_ORDER.map(px)
    expect(sizes).toEqual(sizes.toSorted((a, b) => a - b))
  })

  it('sets the KPI numbers in --fs-3xl, and the off-scale sizes of the spec on the scale', () => {
    expect(sizeOf('live-panel.css', '.kpi__value')).toEqual(['var(--fs-3xl)'])
    expect(sizeOf('live-panel.css', '.spark__rule-label')).toEqual(['var(--fs-2xs)'])
    expect(sizeOf('live-panel.css', '.spark__ticks')).toEqual(['var(--fs-2xs)'])
    expect(sizeOf('shell.css', '.app-nav__count')).toEqual(['var(--fs-2xs)'])
    expect(sizeOf('shell.css', '.integration__mode')).toEqual(['var(--fs-2xs)'])
    expect(sizeOf('base.css', '.mono')).toEqual(['max(0.92em, var(--fs-2xs))'])
  })
})

function presenterBlocks(): { file: string; block: Block }[] {
  return consoleSheets().flatMap(({ name, blocks }) => blocks.filter((b) => b.selector.includes('data-presenter') && b.declarations.some((d) => d.property.startsWith('--fs-'))).map((block) => ({ file: name, block })))
}

describe('presenter mode steps the type scale', () => {
  it('gives each --fs-* token the value of the next larger one, and --fs-4xl stays 44', () => {
    const found = presenterBlocks()
    expect(found).toHaveLength(1)
    const stepped = new Map(found[0].block.declarations.map((d) => [d.property.replace(/^--fs-/, ''), Number.parseFloat(d.value)]))
    const nextUp = TOKEN_ORDER.map((_, i) => px(TOKEN_ORDER[Math.min(i + 1, TOKEN_ORDER.length - 1)]))
    expect(TOKEN_ORDER.map((name) => stepped.get(name))).toEqual(nextUp)
    expect(nextUp).toEqual([12, 13, 14, 15, 17, 20, 26, 34, 44, 44])
  })

  it('reaches the page roots and the header, control bar and footer, never the Overview or the phone frame', () => {
    const [{ block }] = presenterBlocks()
    for (const root of PRESENTER_ROOTS) expect(block.selector).toContain(root)
    expect(block.selector).toContain(".app[data-presenter='on']")
    for (const outside of ['.ov-', '.app--overview', '.phone', '.merchant-page']) expect(block.selector).not.toContain(outside)
    expect(block.declarations.find((d) => d.property === 'font-size')?.value).toBe('var(--fs-base)')
  })
})

describe('motion', () => {
  it('stops every animation and transition under prefers-reduced-motion in base.css', () => {
    const rule = sheet('base.css').blocks.find((b) => b.atRules.some((a) => a.includes('prefers-reduced-motion: reduce')) && b.selector.includes('*'))
    const set = new Map(rule?.declarations.map((d) => [d.property, d.value]))
    expect(set.get('animation-duration')).toBe('1ms !important')
    expect(set.get('animation-iteration-count')).toBe('1 !important')
    expect(set.get('transition-duration')).toBe('1ms !important')
  })

  it('never overrides that rule with an important motion declaration of its own', () => {
    const offenders = consoleSheets().flatMap(({ name, blocks }) =>
      blocks
        .filter((b) => !(name === 'base.css' && b.atRules.some((a) => a.includes('prefers-reduced-motion'))))
        .flatMap((b) => b.declarations.filter((d) => /^(animation|transition)/.test(d.property) && d.value.includes('!important')).map((d) => `${name} ${b.selector} { ${d.property} }`)),
    )
    expect(offenders).toEqual([])
  })
})

// @vitest-environment node
/**
 * Unmapped classes (design system 13.6). The theme clears Tailwind's default palette, radii, fonts, easings, shadows
 * and breakpoints, so a class such as `bg-green-500`, `rounded-xs` or `sm:flex` would build to nothing and fail
 * silently on screen. This test scans src/miniapp exactly as the build does and fails on every such class instead.
 */
import { __unstable__loadDesignSystem, compile } from '@tailwindcss/node'
import { Scanner } from '@tailwindcss/oxide'
import { readFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it } from 'vitest'

const ENTRY = fileURLToPath(new URL('./miniapp.css', import.meta.url))
const BASE = dirname(ENTRY)

/** Utility families whose names come from the theme, and the viewport variants the theme removes. */
const THEMED = /^-?(bg|text|border|ring|outline|fill|stroke|from|via|to|decoration|divide|placeholder|caret|accent|shadow|rounded|font|ease|animate|inset-shadow|drop-shadow)-/
const VIEWPORT = /^(sm|md|lg|xl|2xl):/
/** Words the scanner finds that are not classes (keys and CSS property names in code). Add one here with a reason. */
const NOT_CLASSES = new Set([
  'font-size', // the class-group key in lib/cn.ts
])

/** The utility of a candidate: what follows the last variant colon outside brackets. */
function utilityOf(candidate: string): string {
  let depth = 0
  let start = 0
  for (let index = 0; index < candidate.length; index += 1) {
    const char = candidate[index]
    if (char === '[' || char === '(') depth += 1
    else if (char === ']' || char === ')') depth -= 1
    else if (char === ':' && depth === 0) start = index + 1
  }
  return candidate.slice(start).replace(/^!|!$/g, '')
}

let unmapped: string[] = []
let checked = 0

beforeAll(async () => {
  const css = readFileSync(ENTRY, 'utf8')
  const compiler = await compile(css, { base: BASE, onDependency: () => {} })
  const root = compiler.root === 'none' || compiler.root === null ? [] : [{ ...compiler.root, negated: false }]
  const candidates = new Scanner({ sources: [...root, ...compiler.sources] }).scan()
  const themed = candidates.filter(
    (candidate) => !NOT_CLASSES.has(candidate) && (VIEWPORT.test(candidate) || THEMED.test(utilityOf(candidate))),
  )
  const design = await __unstable__loadDesignSystem(css, { base: BASE })
  const built = design.candidatesToCss(themed)
  checked = themed.length
  unmapped = themed.filter((_candidate, index) => !built[index]).toSorted()
}, 60_000)

describe('mini-app classes', () => {
  it('scans the mini-app source (the check is not vacuous)', () => {
    expect(checked).toBeGreaterThan(50)
  })

  it('every themed class builds to CSS: use the names of design system 13.2 and 13.3', () => {
    expect(unmapped).toEqual([])
  })
})

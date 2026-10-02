/** Guards the scope rules of miniapp.css (ADR 0005): nothing in it may reach the console. */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Read with path APIs. `new URL('./miniapp.css', import.meta.url)` is rewritten by Vite into an http asset
 * URL ("The URL must be of scheme file"), and Vitest blanks any `.css` import, `?raw` included.
 */
const here = dirname(fileURLToPath(import.meta.url))
const withoutComments = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, '')
const source = withoutComments(readFileSync(join(here, 'miniapp.css'), 'utf8'))
const consoleBase = withoutComments(readFileSync(join(here, '..', 'styles', 'base.css'), 'utf8'))

/** The text inside the first brace block that opens at or after `from`, nested blocks included. */
function blockAfter(text: string, from: number): string {
  const open = from < 0 ? -1 : text.indexOf('{', from)
  let depth = 0
  for (let index = open; index >= 0 && index < text.length; index += 1) {
    if (text[index] === '{') depth += 1
    if (text[index] === '}') depth -= 1
    if (depth === 0) return text.slice(open + 1, index)
  }
  return ''
}

const REDUCED_MOTION = /@media\s*\(prefers-reduced-motion:\s*reduce\)/
const importantDeclarations = (block: string) => block.match(/[a-z-]+:\s*[^;{}]+!important/g) ?? []

/** Splits a selector list at its top-level commas, so `:where(a, b)` stays one selector. */
function splitSelectorList(list: string): string[] {
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const char of list) {
    if (char === '(') depth += 1
    if (char === ')') depth -= 1
    if (char === ',' && depth === 0) {
      parts.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  parts.push(current.trim())
  return parts.filter((part) => part !== '')
}

/** Every selector of the stylesheet, at any nesting depth; at-rule preludes are skipped. */
function selectorsOf(text: string): string[] {
  const selectors: string[] = []
  let prelude = ''
  for (const char of text) {
    if (char === '{') {
      const head = prelude.trim()
      if (head !== '' && !head.startsWith('@')) selectors.push(...splitSelectorList(head))
      prelude = ''
    } else if (char === '}' || char === ';') {
      prelude = ''
    } else {
      prelude += char
    }
  }
  return selectors
}

const KEYFRAME_STEP = /^(from|to|\d+(\.\d+)?%)$/

describe('miniapp.css scope', () => {
  it('skips Tailwind preflight: no bare tailwindcss import', () => {
    expect(source).not.toMatch(/@import\s+["']tailwindcss["']/)
    expect(source).not.toMatch(/preflight/)
  })

  it('limits class detection to this folder and marks utilities important', () => {
    expect(source).toMatch(/utilities\.css"\s+layer\(utilities\)\s+source\(none\)\s+important/)
    expect(source).toMatch(/@source\s+"\.\/";/)
  })

  it('never styles :root, html, body or the universal selector outside .miniapp', () => {
    const outside = selectorsOf(source).filter((selector) => !selector.startsWith('.miniapp') && !KEYFRAME_STEP.test(selector))
    expect(outside).toEqual([])
  })

  it('reads at least one .miniapp rule (the guard above is not vacuous)', () => {
    expect(selectorsOf(source).filter((selector) => selector.startsWith('.miniapp')).length).toBeGreaterThan(3)
  })

  it('stops motion under prefers-reduced-motion like the console does, from the base layer', () => {
    // The utilities are layered and !important, so they beat the console's un-layered !important rule in
    // base.css. For !important declarations an earlier layer wins, so base (before utilities) restates it.
    const consoleRule = importantDeclarations(blockAfter(consoleBase, consoleBase.search(REDUCED_MOTION)))
    const baseLayer = blockAfter(source, source.search(/@layer\s+base\s*\{/))
    const miniappRule = blockAfter(baseLayer, baseLayer.search(REDUCED_MOTION))
    expect(consoleRule).toContain('animation-duration: 1ms !important')
    expect(miniappRule).toMatch(/\.miniapp \*,/)
    expect(importantDeclarations(miniappRule)).toEqual(consoleRule)
  })

  it('animates the skeleton with its own keyframes, never the console pulse keyframes', () => {
    expect(source).toMatch(/--animate-pulse:\s*mini-pulse\b/)
    expect(source).toMatch(/@keyframes\s+mini-pulse\b/)
    expect(source).not.toMatch(/@keyframes\s+pulse\b/)
  })
})

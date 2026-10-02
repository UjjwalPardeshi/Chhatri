/**
 * The mini-app CSS as the build ships it (ADR 0005): miniapp.css compiled by the Tailwind compiler that
 * @tailwindcss/vite runs, over the classes it finds in src/miniapp. Once its chunk loads, every rule in it is
 * global, so nothing in it may restyle a console page. A literal word in any mini-app file is enough to emit
 * a utility: "table" would emit `.table { display: table !important }` over the console's own .table.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import { compile, optimize } from '@tailwindcss/node'
import { Scanner } from '@tailwindcss/oxide'
import { beforeAll, describe, expect, it } from 'vitest'

const here = dirname(fileURLToPath(import.meta.url))
const stylesDir = join(here, '..', 'styles')
const consoleCss = readdirSync(stylesDir)
  .filter((name) => name.endsWith('.css'))
  .map((name) => readFileSync(join(stylesDir, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, ''))
  .join('\n')
const matches = (text: string, pattern: RegExp) => new Set([...text.matchAll(pattern)].map((match) => match[1]))
const consoleClasses = matches(consoleCss, /\.(-?[A-Za-z_][\w-]*)/g)
const consoleKeyframes = matches(consoleCss, /@keyframes\s+([\w-]+)/g)
const consoleDefines = matches(consoleCss, /(--[\w-]+)\s*:/g)
const consoleReads = matches(consoleCss, /var\(\s*(--[\w-]+)/g)

type Rule = { selectors: string[]; declarations: string[] }
type Sheet = { rules: Rule[]; keyframes: string[] }

/** `text` split at `separator` where it is not escaped and not inside quotes, brackets or parentheses. */
function splitTopLevel(text: string, separator: string): string[] {
  const parts: string[] = []
  let depth = 0
  let quote = ''
  let start = 0
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    if (char === '\\') index += 1
    else if (quote !== '') quote = char === quote ? '' : quote
    else if (char === '"' || char === "'") quote = char
    else if (char === '(' || char === '[') depth += 1
    else if (char === ')' || char === ']') depth -= 1
    else if (char === separator && depth === 0) {
      parts.push(text.slice(start, index).trim())
      start = index + 1
    }
  }
  return [...parts, text.slice(start).trim()].filter((part) => part !== '')
}

function closingBrace(css: string, open: number): number {
  let depth = 0
  for (let index = open; index < css.length; index += 1) {
    if (css[index] === '{') depth += 1
    if (css[index] === '}') depth -= 1
    if (depth === 0) return index
  }
  throw new Error('unbalanced braces in the compiled CSS')
}

/** Style rules and keyframes names, inside @layer, @media and @supports blocks too. */
function parse(css: string, sheet: Sheet = { rules: [], keyframes: [] }): Sheet {
  let index = 0
  for (let open = css.indexOf('{'); open >= 0; open = css.indexOf('{', index)) {
    const head = (css.slice(index, open).split(';').pop() ?? '').trim()
    const close = closingBrace(css, open)
    const body = css.slice(open + 1, close)
    if (head.startsWith('@keyframes')) sheet.keyframes.push(head.slice('@keyframes'.length).trim())
    else if (/^@(layer|media|supports|container)\b/.test(head)) parse(body, sheet)
    else if (!head.startsWith('@')) sheet.rules.push({ selectors: splitTopLevel(head, ','), declarations: splitTopLevel(body, ';') })
    index = close + 1
  }
  return sheet
}

const SCOPED = /^(\.miniapp\b|:where\(\.miniapp\b)/
const unescape = (name: string) => name.replace(/\\(.)/g, '$1')
const classesOf = (selector: string) => [...selector.matchAll(/\.((?:\\.|[\w-])+)/g)].map((match) => unescape(match[1]))
const selectorsOf = (sheet: Sheet) => sheet.rules.flatMap((rule) => rule.selectors)

/** Classes in every selector that is not scoped under .miniapp: the utilities, which apply on any page. */
const unscopedClasses = (sheet: Sheet) => new Set(selectorsOf(sheet).filter((selector) => !SCOPED.test(selector)).flatMap(classesOf))

/** Rules with a selector that names no class (:root, *, ::backdrop, html, button): they reach every page. */
const globalRules = (sheet: Sheet) =>
  sheet.rules.filter((rule) => rule.selectors.some((selector) => classesOf(selector).length === 0))

type Compiled = {
  sheet: Sheet
  root: unknown
  sources: { base: string; negated: boolean }[]
  files: string[]
  /** The same build with one more word, as if a mini-app file contained it. */
  withWord: (word: string) => Sheet
}
let compiled: Compiled

beforeAll(async () => {
  const css = readFileSync(join(here, 'miniapp.css'), 'utf8')
  const compiler = await compile(css, { base: here, onDependency: () => undefined })
  const scanner = new Scanner({ sources: compiler.sources })
  const candidates = scanner.scan()
  const build = (extra: string[]) => parse(optimize(compiler.build([...candidates, ...extra])).code)
  const sheet = build([])
  compiled = { sheet, root: compiler.root, sources: compiler.sources, files: scanner.files, withWord: (word) => build([word]) }
})

describe('the compiled mini-app CSS', () => {
  it('reads classes from src/miniapp only, test files excluded: automatic source detection is off', () => {
    expect(compiled.root).toBe('none')
    const included = compiled.sources.filter((source) => !source.negated)
    expect(included.map((source) => relative(here, source.base))).toEqual([''])
    expect(compiled.files.length).toBeGreaterThan(17)
    expect(compiled.files.filter((file) => relative(here, file).startsWith('..'))).toEqual([])
    expect(compiled.files.filter((file) => /\.test\.tsx?$/.test(file))).toEqual([])
  })

  it('resets nothing outside .miniapp: its other global rules only set custom properties', () => {
    const global = globalRules(compiled.sheet)
    expect(global.length).toBeGreaterThan(0) // the theme variables and the @property fallback
    const resets = global.filter((rule) => rule.declarations.some((declaration) => !declaration.startsWith('--')))
    expect(resets.map((rule) => rule.selectors.join(', '))).toEqual([])
  })

  it('emits no class that the console styles', () => {
    const emitted = unscopedClasses(compiled.sheet)
    expect(emitted.has('inline-flex')).toBe(true) // the guard does read the utilities
    expect([...consoleClasses].filter((name) => emitted.has(name))).toEqual([])
  })

  it('would catch a console class name written in a mini-app file (the word "table")', () => {
    const emitted = unscopedClasses(compiled.withWord('table'))
    expect([...consoleClasses].filter((name) => emitted.has(name))).toEqual(['table'])
  })

  it('defines no keyframes that the console defines', () => {
    expect(compiled.sheet.keyframes).toContain('mini-pulse')
    expect(compiled.sheet.keyframes.filter((name) => consoleKeyframes.has(name))).toEqual([])
  })

  it('sets no global variable that the console reads but leaves undefined', () => {
    const names = globalRules(compiled.sheet).flatMap((rule) => rule.declarations.map((declaration) => declaration.split(':')[0]))
    const set = new Set(names.map((name) => name.trim()))
    expect(set.has('--spacing')).toBe(true)
    expect([...consoleReads].filter((name) => set.has(name) && !consoleDefines.has(name))).toEqual([])
  })
})

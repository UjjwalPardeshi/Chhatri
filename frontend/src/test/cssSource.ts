/**
 * Reads the console's stylesheets for the CSS guard tests (styles.test.ts, contrast.test.ts). Tests only:
 * a small block parser (selector, enclosing at-rules, declarations) and the token table, so the guards
 * read the same files the browser gets and need no CSS library.
 */
import { readdirSync, readFileSync } from 'node:fs'

const STYLES_DIR = new URL('../styles/', import.meta.url)

export type Declaration = { property: string; value: string }
export type Block = { selector: string; atRules: string[]; declarations: Declaration[] }
export type Sheet = { name: string; blocks: Block[] }

/**
 * Not console pages: the Overview and its map keep their own larger raw sizes and stay outside presenter
 * mode (design system 2.5), and tokens.css holds the scale itself. phone.css (the phone frame) is guarded like the
 * console: every size is on the scale since `.voice__tag` moved from 10.5 px to `--fs-2xs`.
 */
const NOT_CONSOLE: readonly RegExp[] = [/^overview/, /^storm\.css$/, /^tokens\.css$/]

export function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** Every rule block with its declarations; at-rule wrappers (@media, @keyframes) are blocks with no declarations of their own. */
export function parseBlocks(source: string): Block[] {
  const css = stripComments(source)
  const blocks: Block[] = []
  const open: Block[] = []
  let buffer = ''
  let parens = 0
  let quote: string | null = null
  const finishDeclaration = () => {
    const text = buffer.trim()
    buffer = ''
    const colon = text.indexOf(':')
    const block = open.at(-1)
    if (block && colon > 0) block.declarations.push({ property: text.slice(0, colon).trim(), value: text.slice(colon + 1).trim() })
  }
  for (const char of css) {
    if (quote) {
      buffer += char
      if (char === quote) quote = null
      continue
    }
    if (char === '"' || char === "'") quote = char
    if (char === '(') parens += 1
    if (char === ')') parens -= 1
    if (parens === 0 && char === '{') {
      const selector = buffer.trim().replace(/\s+/g, ' ')
      const block: Block = { selector, atRules: open.map((b) => b.selector).filter((s) => s.startsWith('@')), declarations: [] }
      blocks.push(block)
      open.push(block)
      buffer = ''
    } else if (parens === 0 && char === '}') {
      finishDeclaration()
      open.pop()
    } else if (parens === 0 && char === ';') {
      finishDeclaration()
    } else {
      buffer += char
    }
  }
  return blocks
}

function readSheet(name: string): Sheet {
  return { name, blocks: parseBlocks(readFileSync(new URL(name, STYLES_DIR), 'utf8')) }
}

/** The stylesheets of the console pages, header and replay controls. */
export function consoleSheets(): Sheet[] {
  return readdirSync(STYLES_DIR)
    .filter((name) => name.endsWith('.css') && !NOT_CONSOLE.some((skip) => skip.test(name)))
    .toSorted()
    .map(readSheet)
}

export function sheet(name: string): Sheet {
  return readSheet(name)
}

/** The custom properties declared on :root in tokens.css, by name without the leading dashes. */
export function readTokens(): ReadonlyMap<string, string> {
  const tokens = new Map<string, string>()
  for (const block of readSheet('tokens.css').blocks) {
    if (block.selector !== ':root') continue
    for (const { property, value } of block.declarations) if (property.startsWith('--')) tokens.set(property.slice(2), value)
  }
  return tokens
}

// @vitest-environment node
/** Guards the scope rules of miniapp.css by reading the source (design system 13.1, ADR 0005). */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('./miniapp.css', import.meta.url), 'utf8')
const code = css.replace(/\/\*[\s\S]*?\*\//g, '')

describe('miniapp.css source', () => {
  it('imports the theme and the utilities only: no bare tailwindcss import, no Preflight', () => {
    expect(code).not.toMatch(/@import\s+['"]tailwindcss['"]/)
    expect(code).not.toMatch(/preflight/)
    expect(code).toMatch(/@import\s+'tailwindcss\/theme\.css'\s+layer\(theme\)/)
    expect(code).toMatch(/@import\s+'tailwindcss\/utilities\.css'\s+source\(none\)/)
  })

  it('limits class detection to this folder', () => {
    expect(code).toMatch(/@source\s+'\.\/'/)
  })

  it('leaves utilities un-layered and never uses the important flag', () => {
    expect(code).not.toMatch(/utilities\.css'\s+layer\(/)
    expect(code).not.toMatch(/utilities\.css'[^;]*\bimportant\b/)
    expect(code.match(/!important/g) ?? []).toHaveLength(1) // [hidden] in the scoped base, and nothing else
  })

  it('clears every default theme namespace that the mapping replaces', () => {
    for (const name of ['color', 'radius', 'font', 'ease', 'shadow', 'breakpoint']) {
      expect(code).toContain(`--${name}-*: initial;`)
    }
  })

  it('keeps the dark variant inert', () => {
    expect(code).toContain('@custom-variant dark (&:where(.dark, .dark *));')
  })

  it('renames the keyframes the console also defines (spin, pulse)', () => {
    expect(code).toContain('--animate-spin: mini-spin')
    expect(code).toContain('--animate-pulse: mini-pulse')
  })

  it('styles nothing outside .miniapp: the base is :where(.miniapp ...) only', () => {
    const outside = [...code.matchAll(/(^|\})\s*([^{}@]+)\{/gm)]
      .map((match) => (match[2] ?? '').trim())
      .filter((selector) => selector !== '' && !selector.startsWith(':where(.miniapp'))
    // what is left is only the declarations inside @theme, @utility and @keyframes blocks
    expect(outside.filter((s) => /[.#[]|^(html|body|\*|:root)/.test(s))).toEqual([])
  })
})

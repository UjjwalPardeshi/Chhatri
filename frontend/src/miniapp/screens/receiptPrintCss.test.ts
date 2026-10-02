// @vitest-environment node
/** Guards the print rules of the receipt by reading the source (fs-04 10.5, AC-06, AC-30): inside `.miniapp`, no `!important`. */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('./receipt.print.css', import.meta.url), 'utf8')
const css = source.replace(/\/\*[\s\S]*?\*\//g, '')

/** The selector lists of every rule, with the `@media print` wrapper taken off. */
function selectors(): string[] {
  const inner = css.slice(css.indexOf('{') + 1, css.lastIndexOf('}'))
  return [...inner.matchAll(/([^{}]+)\{[^{}]*\}/g)].flatMap((match) => (match[1] ?? '').split(',').map((selector) => selector.trim()))
}

describe('receipt.print.css', () => {
  it('is one @media print block and nothing else', () => {
    expect(css.trim().startsWith('@media print')).toBe(true)
    expect(css.match(/@media/g)).toHaveLength(1)
    expect(css).not.toMatch(/@import|@page|@layer/)
  })

  it('styles only .miniapp, so the console is never printed differently', () => {
    const list = selectors()
    expect(list.length).toBeGreaterThan(0)
    expect(list.filter((selector) => !selector.startsWith('.miniapp'))).toEqual([])
  })

  it('never uses !important', () => {
    expect(css).not.toContain('!important')
  })

  it('hides the app bar, the next-best bar, the tab bar and the toast host in print', () => {
    for (const id of ['app-appbar', 'app-nba', 'app-tabbar', 'app-toast-host']) {
      const rule = new RegExp(`\\[data-testid='${id}'\\][^{}]*\\{[^{}]*display:\\s*none`)
      expect(rule.test(css) || css.includes(`[data-testid='${id}']`)).toBe(true)
    }
    const hidden = [...css.matchAll(/([^{}]+)\{([^{}]*display:\s*none[^{}]*)\}/g)].flatMap((match) => match[1].split(',').map((selector) => selector.trim()))
    for (const id of ['app-appbar', 'app-nba', 'app-tabbar', 'app-toast-host']) expect(hidden.some((selector) => selector.includes(`'${id}'`))).toBe(true)
  })

  it('lets the frame stop clipping so the whole document flows onto the page', () => {
    expect(css).toMatch(/\.miniapp\s*\{[^}]*overflow:\s*visible/)
    expect(css).toMatch(/\.miniapp\s*\{[^}]*contain:\s*none/)
  })
})

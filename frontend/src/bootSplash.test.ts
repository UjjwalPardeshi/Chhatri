// @vitest-environment node
/**
 * The first paint before the bundle runs (finding: "cold first load shows a blank navy screen"): index.html shows a
 * visible line and a small CSS spinner on both grounds, and the spinner stops under reduced motion.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')

describe('boot splash', () => {
  it('says what is loading and draws a spinner inside #root', () => {
    const root = html.slice(html.indexOf('<div id="root">'), html.indexOf('</body>'))
    expect(root).toContain('Chhatri · loading the console…')
    expect(root).toContain('boot-splash__spinner')
    expect(root).toContain('role="status"')
  })

  it('colours the line for the paper ground and for the navy one, and stops the spin under reduced motion', () => {
    expect(html).toMatch(/\.boot-splash__text\s*\{[^}]*color:\s*#/)
    expect(html).toMatch(/html\[data-route='overview'\] \.boot-splash__text\s*\{[^}]*color:\s*#fff/)
    expect(html).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.boot-splash__spinner\s*\{[^}]*animation:\s*none/)
  })
})

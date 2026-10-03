import { describe, expect, it } from 'vitest'

import { contextTooltipHtml, heatBlurPx } from './heat'

describe('heat wash', () => {
  it('blurs by about half a cell, clamped for far and near zooms', () => {
    expect(heatBlurPx(5, 19)).toBe(3)
    expect(heatBlurPx(18, 19)).toBe(22)
    const city = heatBlurPx(12, 19)
    expect(city).toBeGreaterThan(8)
    expect(city).toBeLessThan(16)
  })

  it('labels a context cell as simulated, with the place name escaped', () => {
    const html = contextTooltipHtml('Thane <b>', 94)
    expect(html).toContain('Thane &lt;b&gt; · 94% of expected')
    expect(html).toContain('Simulated context · not covered, no payout')
  })
})

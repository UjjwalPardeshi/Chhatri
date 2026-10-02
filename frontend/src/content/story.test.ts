/** The Overview's rain-day thread says who paused the instalment: the lender once it decides (X4), else the BUILT line. */
import { describe, expect, it } from 'vitest'

import { instalmentLine } from './story'

describe('instalmentLine', () => {
  it('keeps the BUILT pause line while x4_lender_request is off', () => {
    expect(instalmentLine('')).toEqual({ hi: 'कल की ₹600 की किस्त रोक दी गई है।', en: "Tomorrow's ₹600 instalment is paused." })
  })

  it("names the lender while x4_lender_request is on, and never says Chhatri paused it", () => {
    const line = instalmentLine('n1_miniapp,x4_lender_request')
    expect(line.en).toBe("Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty.")
    expect(line.hi).toContain('आपके लेंडर ने')
    expect(line.en).not.toMatch(/chhatri paused/i)
  })
})

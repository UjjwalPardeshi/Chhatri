/** Default zone card choice on the live map (SPEC §20). */
import { describe, expect, it } from 'vitest'

import type { StateSnapshot } from '../api/types'
import { defaultZone } from './Live'

const snap = (triggers: string[], zones: string[]) =>
  ({ triggers: triggers.map((zone_id) => ({ zone_id })), zones: zones.map((zone_id) => ({ zone_id })) }) as unknown as StateSnapshot

describe('defaultZone', () => {
  it('prefers the merchant zone when it triggered, then the first trigger, then the merchant zone', () => {
    expect(defaultZone(snap(['Z3', 'Z7'], ['Z1']), 'Z7')).toBe('Z7')
    expect(defaultZone(snap(['Z3'], ['Z1']), 'Z7')).toBe('Z3')
    expect(defaultZone(snap([], ['Z1']), 'Z7')).toBe('Z7')
    expect(defaultZone(snap([], ['Z1']), null)).toBe('Z1')
    expect(defaultZone(snap([], []), null)).toBeNull()
  })
})

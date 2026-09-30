/** Watch launchers stop at the end of their story beat (SPEC §17.2 monsoon timeline). */
import { describe, expect, it } from 'vitest'

import type { ClockState } from '../api/types'
import { LAUNCHES } from '../content/deck'
import { shouldStop } from './stopAt'

const clock = (now: string, running = true, scenario: ClockState['scenario'] = 'monsoon') => ({ now: `2025-08-19T${now}:00+05:30`, running, scenario }) as ClockState

describe('stop at the story beat', () => {
  it('pauses a running replay of the same scenario once the beat is reached', () => {
    const stop = { scenario: 'monsoon', at: '17:06' } as const
    expect(shouldStop(stop, clock('17:05'))).toBe(false)
    expect(shouldStop(stop, clock('17:06'))).toBe(true)
    expect(shouldStop(stop, clock('17:09'))).toBe(true)
    expect(shouldStop(stop, clock('17:07', false))).toBe(false)
    expect(shouldStop(stop, clock('17:07', true, 'illness'))).toBe(false)
    expect(shouldStop(null, clock('17:07'))).toBe(false)
  })

  it('ends the storm launchers just after the 17:05 instalment pause', () => {
    expect(LAUNCHES.stormLive.pauseAt).toBe('17:06')
    expect(LAUNCHES.rainDay.pauseAt).toBe('17:06')
  })
})

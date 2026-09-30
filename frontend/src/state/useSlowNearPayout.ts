/**
 * "Slow near payout" (SPEC §17.2 monsoon timeline, §17.1 speed): at the default 6 simulated
 * minutes per second the 17:00 trigger, 17:04 credit and 17:05 pause flash by in under a second.
 * While the replay plays through the scenario's slow window (content/chapters.ts) the console asks
 * for 1 minute per second, then restores the presenter's speed once the window is behind it. A
 * speed the presenter picks inside the window wins until the window ends. The preference is a
 * per-viewer convenience kept in localStorage (on by default); it never changes the replay itself.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ClockState } from '../api/types'
import { inWindow, SLOW_SPEED, SLOW_WINDOWS, type SlowWindow } from '../content/chapters'
import { hhmm } from '../lib/time'
import type { ReplayAction } from './live'

export const SLOW_PREF_KEY = 'chhatri.slowNearPayout'

export type SlowMemory = { saved: number | null; overridden: boolean }
export type SlowInput = { now: string; running: boolean; speed: number; slowWindow: SlowWindow | null; enabled: boolean; memory: SlowMemory }
export type SlowDecision = { play: number | null; memory: SlowMemory }

const EMPTY: SlowMemory = Object.freeze({ saved: null, overridden: false }) as SlowMemory

/** What to do for one clock update: a speed to ask for (or null) and the new memory. */
export function slowDecision({ now, running, speed, slowWindow, enabled, memory }: SlowInput): SlowDecision {
  const inside = slowWindow !== null && inWindow(hhmm(now), slowWindow)
  if (!inside) {
    const restore = running && memory.saved !== null && speed === SLOW_SPEED ? memory.saved : null
    return { play: restore, memory: running || memory.saved === null ? EMPTY : memory }
  }
  if (!enabled || memory.overridden || memory.saved !== null || !running || speed <= SLOW_SPEED) return { play: null, memory }
  return { play: SLOW_SPEED, memory: { saved: speed, overridden: false } }
}

function readPreference(): boolean {
  try {
    return window.localStorage.getItem(SLOW_PREF_KEY) !== '0'
  } catch (error) {
    console.warn('[replay] slow-near-payout preference unavailable', error)
    return true
  }
}

function writePreference(on: boolean): void {
  try {
    window.localStorage.setItem(SLOW_PREF_KEY, on ? '1' : '0')
  } catch (error) {
    console.warn('[replay] could not store the slow-near-payout preference', error)
  }
}

type Replay = (action: ReplayAction, arg?: string | number) => Promise<void>

export type SlowNearPayout = { available: boolean; enabled: boolean; setEnabled: (on: boolean) => void; noteManualSpeed: () => void }

export function useSlowNearPayout(clock: ClockState | null, replay: Replay, busy: boolean): SlowNearPayout {
  const [enabled, setEnabledState] = useState(readPreference)
  const memory = useRef<SlowMemory>(EMPTY)
  const slowWindow = clock?.scenario ? SLOW_WINDOWS[clock.scenario] : null
  useEffect(() => {
    if (!clock || busy) return
    const decision = slowDecision({ now: clock.now, running: clock.running, speed: clock.speed, slowWindow, enabled, memory: memory.current })
    memory.current = decision.memory
    if (decision.play !== null) void replay('play', decision.play)
  }, [clock, slowWindow, enabled, busy, replay])
  const setEnabled = useCallback((on: boolean) => {
    writePreference(on)
    setEnabledState(on)
  }, [])
  /** The presenter picked a speed: inside the window it wins, outside nothing is remembered. */
  const noteManualSpeed = useCallback(() => {
    memory.current = { saved: null, overridden: true }
  }, [])
  return { available: slowWindow !== null, enabled, setEnabled, noteManualSpeed }
}

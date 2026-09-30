/**
 * Where a "watch it happen" launcher stops (SPEC §17.2 monsoon timeline: trigger 17:00, credits
 * 17:04, instalment pauses 17:05). The launcher plays the replay slowly through the story beat and
 * the console pauses it once the clock reaches `at`, so the map and the phone hold the moment the
 * presenter talks over instead of drifting on to 20:00. Any replay control the presenter touches
 * cancels the stop (live.tsx).
 */
import type { ClockState, ScenarioName } from '../api/types'
import { hhmm } from '../lib/time'

export type StopAt = { scenario: ScenarioName; at: string }

export function shouldStop(stop: StopAt | null, clock: Pick<ClockState, 'now' | 'running' | 'scenario'>): boolean {
  if (!stop || !clock.running || clock.scenario !== stop.scenario) return false
  return hhmm(clock.now) >= stop.at
}

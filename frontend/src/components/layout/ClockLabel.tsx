/**
 * The replay clock (SPEC §19.2 ClockState.label "Mumbai · monsoon replay · 17:00 · simulated",
 * §20 header). The exact label string and order stay; only its parts are styled: the HH:MM is the
 * largest changing number in the demo, so it reads from the back of the room, and it flashes blue
 * for a moment whenever money moves in that minute (trigger, credit, instalment pause).
 */
import { useState } from 'react'

import type { ClockState } from '../../api/types'
import { useLiveEvent } from '../../state/live'

/** Parts of the SPEC §19.2 label "Mumbai · monsoon replay · 17:00 · simulated" (null if shaped otherwise). */
export function clockParts(label: string): { city: string; scenario: string; time: string; tail: string } | null {
  const parts = label.split(' · ')
  if (parts.length !== 4) return null
  const [city, scenario, time, tail] = parts
  return { city, scenario, time, tail }
}

/** Splits "Mumbai · monsoon replay · 17:00 · simulated" so "simulated" can be de-emphasised. */
export function splitClockLabel(label: string): { main: string; tail: string } {
  const at = label.lastIndexOf(' · ')
  return at === -1 ? { main: label, tail: '' } : { main: label.slice(0, at), tail: label.slice(at + 3) }
}

/** Events that move money or start a claim: the clock flashes when one arrives. */
export const PULSE_EVENTS = ['trigger', 'payout', 'instalment'] as const

export function ClockLabel({ clock }: { clock: ClockState }) {
  const [pulse, setPulse] = useState(0)
  useLiveEvent(PULSE_EVENTS, () => setPulse((n) => n + 1))
  const parts = clockParts(clock.label)
  const { main, tail } = splitClockLabel(clock.label)
  return (
    <div className="clock-label" data-running={clock.running} aria-live="off">
      <span className="clock-label__dot" />
      {parts ? (
        <span className="clock-label__main">
          <span className="clock-label__city">{parts.city} · </span>
          {parts.scenario} ·{' '}
          <span key={pulse} className="clock-label__time" data-pulse={pulse > 0}>
            {parts.time}
          </span>
        </span>
      ) : (
        <span className="clock-label__main">{main}</span>
      )}
      {tail ? <span className="clock-label__tail"> · {tail}</span> : null}
    </div>
  )
}

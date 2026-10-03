/**
 * Seek to a typed time (SPEC §17.1): the form checks the HH:MM shape and the scenario's window before anything is
 * posted, and says what to type in Hindi and English (finding: "seek outside the window shows a raw developer error").
 * A 422 the server still answers for a seek reads as the same window line in the control bar (`friendlyReplayError`).
 */
import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { isHhmm } from '../../api/endpoints'
import type { ClockState } from '../../api/types'
import { minuteOfDay } from '../../content/chapters'
import { hhmm } from '../../lib/time'

export type SeekLine = { hi: string; en: string }

const FORMAT_LINE: SeekLine = { hi: 'समय HH:MM में लिखें, जैसे 17:00।', en: 'Type the time as HH:MM, for example 17:00.' }

function windowLine(clock: Pick<ClockState, 'start' | 'end'>): SeekLine {
  const start = hhmm(clock.start)
  const end = hhmm(clock.end)
  return { hi: `समय ${start} से ${end} के बीच चुनें।`, en: `Pick a time between ${start} and ${end}.` }
}

/** Null when `value` is an HH:MM inside the scenario's window; otherwise the line that says what to type. */
export function seekProblem(value: string, clock: Pick<ClockState, 'start' | 'end'>): SeekLine | null {
  const to = value.trim()
  if (!isHhmm(to)) return FORMAT_LINE
  const minute = minuteOfDay(to)
  const start = minuteOfDay(hhmm(clock.start))
  const end = minuteOfDay(hhmm(clock.end))
  if (minute === null || start === null || end === null) return null
  return minute < start || minute > end ? windowLine(clock) : null
}

/** The window line for a seek the server refused (422 on `to`); null for every other error. */
export function friendlyReplayError(error: unknown, clock: Pick<ClockState, 'start' | 'end'> | null): SeekLine | null {
  if (!(error instanceof ApiError) || error.code !== 'validation_error' || !('to' in error.fields)) return null
  return clock ? windowLine(clock) : FORMAT_LINE
}

export function SeekLineText({ line }: { line: SeekLine }) {
  return (
    <>
      <span className="hi" lang="hi">
        {line.hi}
      </span>{' '}
      {line.en}
    </>
  )
}

export function SeekForm({ clock, onSeek, busy }: { clock: ClockState; onSeek: (to: string) => void; busy: boolean }) {
  const [value, setValue] = useState('')
  const [problem, setProblem] = useState<SeekLine | null>(null)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = seekProblem(value, clock)
    setProblem(found)
    if (found === null) onSeek(value.trim())
  }
  return (
    <form className="seek" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="seek-input">
        Seek to time (HH:MM)
      </label>
      <input
        id="seek-input"
        className={`input seek__input ${problem ? 'is-invalid' : ''}`}
        value={value}
        placeholder="HH:MM"
        inputMode="numeric"
        maxLength={5}
        aria-invalid={problem !== null}
        aria-describedby={problem ? 'seek-problem' : undefined}
        title={`Seek between ${hhmm(clock.start)} and ${hhmm(clock.end)} (HH:MM)`}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit" className="btn" disabled={busy}>
        Seek
      </button>
      {problem ? (
        <p id="seek-problem" role="alert" className="seek__problem">
          <SeekLineText line={problem} />
        </p>
      ) : null}
    </form>
  )
}

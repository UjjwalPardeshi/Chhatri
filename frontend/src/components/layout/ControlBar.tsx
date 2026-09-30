/**
 * Replay controls (SPEC §17.1, §19 /api/replay/*, §20 header): scenario picker, clock label,
 * play/pause, speed (1–120 simulated minutes per real second), step, seek HH:MM, reset.
 */
import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { isHhmm, MAX_SPEED, MIN_SPEED } from '../../api/endpoints'
import { SCENARIO_NAMES, type ClockState, type ScenarioName } from '../../api/types'
import { hhmm, minutesBetween } from '../../lib/time'
import { useLive } from '../../state/live'
import { Icon } from '../common/Icon'
import { InlineError } from '../common/Status'

export const SCENARIO_OPTIONS: Readonly<Record<ScenarioName, { label: string; merchant: string }>> = Object.freeze({
  monsoon: { label: 'Monsoon replay · Tue 19 Aug', merchant: 'S-0142' },
  illness: { label: 'Anil falls ill · Thu 21 Aug', merchant: 'S-0142' },
  illness_mismatch: { label: 'Slip name mismatch · Thu 21 Aug', merchant: 'S-0142' },
  buy_cover: { label: 'Cover after an alert · Mon 18 Aug', merchant: 'S-0907' },
})

const FULL_PCT = 100

export const SPEED_CHOICES: readonly number[] = [MIN_SPEED, 2, 6, 15, 30, 60, MAX_SPEED]
export const STEP_CHOICES: readonly { minutes: number; label: string }[] = [
  { minutes: 1, label: '+1 min' },
  { minutes: 15, label: '+15 min' },
  { minutes: 60, label: '+1 h' },
]

/** Splits "Mumbai · monsoon replay · 17:00 · simulated" so "simulated" can be de-emphasised. */
export function splitClockLabel(label: string): { main: string; tail: string } {
  const at = label.lastIndexOf(' · ')
  return at === -1 ? { main: label, tail: '' } : { main: label.slice(0, at), tail: label.slice(at + 3) }
}

export function progressPct(clock: ClockState): number {
  const span = minutesBetween(clock.start, clock.end)
  const done = minutesBetween(clock.start, clock.now)
  if (!span || done === null) return 0
  return Math.min(100, Math.max(0, (done / span) * 100))
}

/** Parts of the SPEC §19.2 label "Mumbai · monsoon replay · 17:00 · simulated" (null if shaped otherwise). */
export function clockParts(label: string): { city: string; scenario: string; time: string; tail: string } | null {
  const parts = label.split(' · ')
  if (parts.length !== 4) return null
  const [city, scenario, time, tail] = parts
  return { city, scenario, time, tail }
}

function ClockLabel({ clock }: { clock: ClockState }) {
  const parts = clockParts(clock.label)
  const { main, tail } = splitClockLabel(clock.label)
  return (
    <div className="clock-label" data-running={clock.running} aria-live="off">
      <span className="clock-label__dot" />
      {parts ? (
        <span className="clock-label__main">
          <span className="clock-label__city">{parts.city} · </span>
          {parts.scenario} · <span className="clock-label__time">{parts.time}</span>
        </span>
      ) : (
        <span className="clock-label__main">{main}</span>
      )}
      {tail ? <span className="clock-label__tail"> · {tail}</span> : null}
    </div>
  )
}

function SeekForm({ clock, onSeek, busy }: { clock: ClockState; onSeek: (to: string) => void; busy: boolean }) {
  const [value, setValue] = useState('')
  const [invalid, setInvalid] = useState(false)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const to = value.trim()
    if (!isHhmm(to)) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    onSeek(to)
  }
  return (
    <form className="seek" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="seek-input">
        Seek to time (HH:MM)
      </label>
      <input
        id="seek-input"
        className={`input seek__input ${invalid ? 'is-invalid' : ''}`}
        value={value}
        placeholder="HH:MM"
        inputMode="numeric"
        maxLength={5}
        aria-invalid={invalid}
        title={`Seek between ${hhmm(clock.start)} and ${hhmm(clock.end)}`}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit" className="btn" disabled={busy}>
        Seek
      </button>
    </form>
  )
}

export function ControlBar() {
  const { snapshot, replay, replayBusy, replayError } = useLive()
  const navigate = useNavigate()
  const location = useLocation()
  const clock = snapshot?.clock ?? null
  /** A speed picked while paused; it yields to the server's speed once that changes. */
  const [picked, setPicked] = useState<{ server: number; speed: number } | null>(null)
  const [dismissed, setDismissed] = useState<typeof replayError>(null)
  /** Phones fold speed, steps, seek and reset into a "More" popover (CSS shows it inline elsewhere). */
  const [moreOpen, setMoreOpen] = useState(false)

  if (!clock) return <div className="control-bar control-bar--empty">Waiting for the replay clock…</div>
  const busy = replayBusy !== null
  const speed = picked?.server === clock.speed ? picked.speed : clock.speed

  const changeScenario = async (name: ScenarioName) => {
    await replay('load', name)
    if (location.pathname.startsWith('/merchant/')) navigate(`/merchant/${SCENARIO_OPTIONS[name].merchant}`)
  }
  const changeSpeed = (next: number) => {
    setPicked({ server: clock.speed, speed: next })
    if (clock.running) void replay('play', next)
  }

  return (
    <div className="control-bar">
      <label className="visually-hidden" htmlFor="scenario-select">
        Scenario
      </label>
      <select id="scenario-select" className="input scenario-select" value={clock.scenario ?? ''} disabled={busy} onChange={(e) => void changeScenario(e.target.value as ScenarioName)}>
        {SCENARIO_NAMES.map((name) => (
          <option key={name} value={name}>
            {SCENARIO_OPTIONS[name].label}
          </option>
        ))}
      </select>
      <ClockLabel clock={clock} />
      <fieldset className="transport" aria-label="Replay controls">
        <button type="button" className="btn btn--primary transport__play" disabled={busy} aria-label={clock.running ? 'Pause' : 'Play'} onClick={() => void (clock.running ? replay('pause') : replay('play', speed))}>
          <Icon name={clock.running ? 'pause' : 'play'} size={16} />
          {clock.running ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="btn btn--icon transport__more-toggle" aria-expanded={moreOpen} aria-controls="transport-more" aria-label="More replay controls" onClick={() => setMoreOpen((v) => !v)}>
          <Icon name="more" size={16} />
        </button>
        <div id="transport-more" className="transport__more" data-open={moreOpen}>
          <label className="speed">
            <span className="visually-hidden">Speed (simulated minutes per second)</span>
            <select className="input" value={speed} onChange={(e) => changeSpeed(Number(e.target.value))} aria-label="Speed">
              {SPEED_CHOICES.map((s) => (
                <option key={s} value={s}>
                  {s} min/s
                </option>
              ))}
            </select>
          </label>
          {STEP_CHOICES.map((choice) => (
            <button key={choice.minutes} type="button" className="btn" disabled={busy} onClick={() => void replay('step', choice.minutes)}>
              {choice.label}
            </button>
          ))}
          <SeekForm key={`${clock.scenario}|${clock.start}`} clock={clock} busy={busy} onSeek={(to) => void replay('seek', to)} />
          <button type="button" className="btn btn--icon" disabled={busy} aria-label="Reset" title="Reset to the scenario start" onClick={() => void replay('reset')}>
            <Icon name="reset" size={16} />
          </button>
        </div>
      </fieldset>
      {replayError && replayError !== dismissed ? (
        <div className="control-bar__error">
          <InlineError error={replayError} onDismiss={() => setDismissed(replayError)} />
        </div>
      ) : null}
      <div className="control-bar__progress" style={{ transform: `scaleX(${progressPct(clock) / FULL_PCT})` }} />
    </div>
  )
}

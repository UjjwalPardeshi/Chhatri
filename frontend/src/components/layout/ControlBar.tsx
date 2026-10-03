/**
 * Replay controls (SPEC §17.1, §19 /api/replay/*, §20 header): scenario picker, clock label,
 * play/pause, speed (1–120 simulated minutes per real second), step, seek HH:MM, reset, the
 * "Slow near payout" switch, and the scrubber with the scenario's chapters underneath.
 */
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { MAX_SPEED, MIN_SPEED } from '../../api/endpoints'
import { SCENARIO_NAMES, type ClockState, type ScenarioName } from '../../api/types'
import { minutesBetween } from '../../lib/time'
import { useLive } from '../../state/live'
import { useSlowNearPayout, type SlowNearPayout } from '../../state/useSlowNearPayout'
import { Icon } from '../common/Icon'
import { InlineError } from '../common/Status'
import { Feature } from '../common/Feature'
import { ClockLabel } from './ClockLabel'
import { PresenterKeysButton } from './PresenterControls'
import { Scrubber } from './Scrubber'
import { friendlyReplayError, SeekForm, SeekLineText } from './SeekForm'
import { usePresenterKeys } from './usePresenterKeys'

export { clockParts, splitClockLabel } from './ClockLabel'

/** Scenario picker labels and each scenario's demo merchant (binding decision B5). */
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

export function progressPct(clock: ClockState): number {
  const span = minutesBetween(clock.start, clock.end)
  const done = minutesBetween(clock.start, clock.now)
  if (!span || done === null) return 0
  return Math.min(FULL_PCT, Math.max(0, (done / span) * FULL_PCT))
}

/** Rendered twice: beside the scrubber on wide screens, inside the "More" popover on phones (CSS). */
function SlowToggle({ slow, placement }: { slow: SlowNearPayout; placement: 'bar' | 'menu' }) {
  if (!slow.available) return null
  return (
    <label className={`slow-toggle slow-toggle--${placement}`} title="Play 16:58 to 17:06 at 1 simulated minute per second, then go back to the chosen speed">
      <input type="checkbox" checked={slow.enabled} onChange={(e) => slow.setEnabled(e.target.checked)} />
      <span className="slow-toggle__switch" aria-hidden="true" />
      Slow near payout
    </label>
  )
}

type TransportProps = { clock: ClockState; busy: boolean; speed: number; slow: SlowNearPayout; onSpeed: (speed: number) => void }

function Transport({ clock, busy, speed, slow, onSpeed }: TransportProps) {
  const { replay } = useLive()
  /** Phones fold speed, steps, seek and reset into a "More" popover (CSS shows it inline elsewhere); a seek or reset closes it. */
  const [moreOpen, setMoreOpen] = useState(false)
  /** Esc closes the menu, wherever it shows (phones always, presenter mode on any screen). */
  useEffect(() => {
    if (!moreOpen) return undefined
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMoreOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [moreOpen])
  return (
    <fieldset className="transport" aria-label="Replay controls">
      <button type="button" className="btn btn--primary transport__play" disabled={busy} aria-label={clock.running ? 'Pause' : 'Play'} onClick={() => void (clock.running ? replay('pause') : replay('play', speed))}>
        <Icon name={clock.running ? 'pause' : 'play'} size={16} />
        {clock.running ? 'Pause' : 'Play'}
      </button>
      <button type="button" className="btn btn--icon transport__more-toggle" aria-expanded={moreOpen} aria-controls="transport-more" aria-label="More replay controls" onClick={() => setMoreOpen((v) => !v)}>
        <Icon name="more" size={16} />
      </button>
      <Feature name="console_polish">
        <PresenterKeysButton />
      </Feature>
      <div id="transport-more" className="transport__more" data-open={moreOpen}>
        <label className="speed">
          <span className="visually-hidden">Speed (simulated minutes per second)</span>
          <select className="input" value={speed} onChange={(e) => onSpeed(Number(e.target.value))} aria-label="Speed">
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
        <SeekForm
          key={`${clock.scenario}|${clock.start}`}
          clock={clock}
          busy={busy}
          onSeek={(to) => {
            setMoreOpen(false)
            void replay('seek', to)
          }}
        />
        <button
          type="button"
          className="btn btn--icon"
          disabled={busy}
          aria-label="Reset"
          title="Reset to the scenario start"
          onClick={() => {
            setMoreOpen(false)
            void replay('reset')
          }}
        >
          <Icon name="reset" size={16} />
        </button>
        <SlowToggle slow={slow} placement="menu" />
      </div>
    </fieldset>
  )
}

/** A failed replay control: a refused seek in plain words (Hindi and English), anything else as the API said it. */
function ReplayError({ error, clock, onDismiss }: { error: NonNullable<ReturnType<typeof useLive>['replayError']>; clock: ClockState; onDismiss: () => void }) {
  const friendly = friendlyReplayError(error, clock)
  return (
    <div className="control-bar__error">
      {friendly ? (
        <p role="alert" className="seek__problem">
          <SeekLineText line={friendly} />{' '}
          <button type="button" className="btn" onClick={onDismiss}>
            Dismiss
          </button>
        </p>
      ) : (
        <InlineError error={error} onDismiss={onDismiss} />
      )}
    </div>
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
  const busy = replayBusy !== null
  const slow = useSlowNearPayout(clock, replay, busy)
  const speed = clock ? (picked?.server === clock.speed ? picked.speed : clock.speed) : 0
  usePresenterKeys({ clock, busy, speed, slow, replay })

  if (!clock) return <div className="control-bar control-bar--empty">Waiting for the replay clock…</div>

  const changeScenario = async (name: ScenarioName) => {
    await replay('load', name)
    if (location.pathname.startsWith('/merchant/')) navigate(`/merchant/${SCENARIO_OPTIONS[name].merchant}`)
  }
  const changeSpeed = (next: number) => {
    setPicked({ server: clock.speed, speed: next })
    slow.noteManualSpeed()
    if (clock.running) void replay('play', next)
  }

  return (
    <div className="control-bar">
      <div className="control-bar__row">
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
        <Transport clock={clock} busy={busy} speed={speed} slow={slow} onSpeed={changeSpeed} />
      </div>
      <Scrubber clock={clock} busy={busy} onSeek={(to) => void replay('seek', to)} extra={<SlowToggle slow={slow} placement="bar" />} />
      {replayError && replayError !== dismissed ? <ReplayError error={replayError} clock={clock} onDismiss={() => setDismissed(replayError)} /> : null}
    </div>
  )
}

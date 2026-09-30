/**
 * A button that jumps into the live demo (SPEC §17.2 scenarios via useLaunch). Every launcher on
 * the Overview and Policy pages uses it, so labels, busy text and the nested arrow look the same.
 */
import { LAUNCHES, type LaunchKey } from '../../content/deck'
import type { LaunchState } from '../../state/useLaunch'
import { Icon } from '../common/Icon'

type Props = {
  launcher: LaunchState
  /** Busy/error key; defaults to the launch key. */
  id?: string
  target: LaunchKey
  label: string
  busyLabel?: string
  tone?: 'primary' | 'ghost' | 'quiet' | 'link'
}

export function LaunchButton({ launcher, id, target, label, busyLabel = 'Loading…', tone = 'primary' }: Props) {
  const key = id ?? target
  const busy = launcher.busy === key
  return (
    <button type="button" className={`ov-btn ov-btn--${tone}`} disabled={launcher.busy !== null} aria-busy={busy} onClick={() => void launcher.launch(key, LAUNCHES[target])}>
      <span className="ov-btn__label">{busy ? busyLabel : label}</span>
      {tone === 'primary' ? (
        <span className="ov-btn__icon" aria-hidden="true">
          <Icon name="arrow" size={16} />
        </span>
      ) : null}
    </button>
  )
}

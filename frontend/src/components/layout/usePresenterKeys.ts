/**
 * The presenter shortcuts that drive the replay (fs-08 12.3): Space plays or pauses, 1 to 4 jump to a chapter (a minute
 * before it, as clicking the tick does) and S switches "Slow near payout" and W opens or closes the what-if drawer on /live (flag h24_whatif). They live with the controls they press and
 * listen only while presenter mode is on; P, ? and Esc belong to the mode itself (state/presenter.tsx).
 */
import { useEffect } from 'react'

import type { ClockState } from '../../api/types'
import { minuteBefore } from '../../content/chapters'
import { isFeatureEnabled } from '../../features'
import type { ReplayAction } from '../../state/live'
import { presenterKeyAction, usePresenter } from '../../state/presenter'
import { useLatest } from '../../state/useLatest'
import type { SlowNearPayout } from '../../state/useSlowNearPayout'
import { requestWhatIfToggle } from '../../state/whatIfToggle'
import { chaptersOnTrack } from './Scrubber'

export type PresenterControlsState = {
  clock: ClockState | null
  busy: boolean
  /** The speed Play asks for (the picked one while paused). */
  speed: number
  slow: SlowNearPayout
  replay: (action: ReplayAction, arg?: string | number) => Promise<void>
}

export function usePresenterKeys(controls: PresenterControlsState): void {
  const { on } = usePresenter()
  const latest = useLatest(controls)
  useEffect(() => {
    if (!on) return undefined
    const onKey = (event: KeyboardEvent) => {
      const action = presenterKeyAction(event)
      const { clock, busy, speed, slow, replay } = latest.current
      if (!action || !clock) return
      if (action.type === 'playPause') {
        event.preventDefault()
        if (!busy) void (clock.running ? replay('pause') : replay('play', speed))
      } else if (action.type === 'chapter') {
        const chapter = chaptersOnTrack(clock)[action.index]
        if (!chapter) return
        event.preventDefault()
        if (!busy) void replay('seek', minuteBefore(chapter.at))
      } else if (action.type === 'slow' && slow.available) {
        slow.setEnabled(!slow.enabled)
      } else if (action.type === 'whatif' && isFeatureEnabled('h24_whatif')) {
        event.preventDefault()
        requestWhatIfToggle()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [on, latest])
}

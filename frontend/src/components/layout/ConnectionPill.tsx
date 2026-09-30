/** Small "reconnecting" pill while the SSE stream is down (SPEC §20 "Resilience"). */
import { useLive } from '../../state/live'

export function ConnectionPill() {
  const { stream } = useLive()
  if (stream === 'open' || stream === 'closed') return null
  const label = stream === 'connecting' ? 'Connecting…' : 'Reconnecting…'
  return (
    <output className="connection-pill" aria-live="polite" data-state={stream}>
      <span className="connection-pill__dot" />
      {label}
    </output>
  )
}

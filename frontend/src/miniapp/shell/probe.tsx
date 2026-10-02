/** A test probe: the URL the shell wrote, the state of the event stream, and a history Back button (the browser's Back). */
import { useLocation, useNavigate } from 'react-router'

import { useLive } from '../../state/live'

export function Probe() {
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const { stream } = useLive()
  return (
    <div>
      <output data-testid="probe-location" data-stream={stream}>
        {pathname + search}
      </output>
      <button type="button" data-testid="probe-history-back" onClick={() => void navigate(-1)}>
        history back
      </button>
    </div>
  )
}

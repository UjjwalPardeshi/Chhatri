/** The closing band after the team (a way into the demo from the end of the page). */
import type { LaunchState } from '../../state/useLaunch'
import { LaunchButton } from './LaunchButton'
import { LaunchError } from './LaunchError'

export const CLOSING_KEYS = ['end-storm', 'end-phone', 'end-case'] as const

export function Closing({ launcher }: { launcher: LaunchState }) {
  return (
    <section className="ov-closing" aria-label="See it live">
      <div className="ov-closing__inner">
        <h2 className="ov-closing__title">Now watch it happen, live.</h2>
        <div className="ov-closing__ctas">
          <LaunchButton launcher={launcher} id="end-storm" target="stormLive" label="Watch the storm replay" busyLabel="Loading the storm…" />
          <LaunchButton launcher={launcher} id="end-phone" target="questions" tone="ghost" label="See Anil’s WhatsApp" busyLabel="Opening the phone…" />
          <LaunchButton launcher={launcher} id="end-case" target="reviewCase" tone="ghost" label="Review case C-2291" busyLabel="Opening the case…" />
        </div>
        <LaunchError launcher={launcher} keys={CLOSING_KEYS} />
      </div>
    </section>
  )
}

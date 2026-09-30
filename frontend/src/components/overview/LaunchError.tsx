/** Inline error for a failed scenario jump, shown next to the buttons that asked for it. */
import type { LaunchState } from '../../state/useLaunch'
import { InlineError } from '../common/Status'

export function LaunchError({ launcher, keys }: { launcher: LaunchState; keys: readonly string[] }) {
  const error = launcher.errorFor(keys)
  return error ? <InlineError error={error} /> : null
}

/**
 * The three live tests (deck slide 8, SPEC §0 item 5, §13.6): EXPLAINED, HUMAN, BLOCKED, each with
 * a "Run it" launcher into the scenario that shows it. One component for the Overview and /policy.
 */
import { LAUNCHES, LIVE_TESTS } from '../../content/deck'
import type { LaunchState } from '../../state/useLaunch'
import { Icon } from '../common/Icon'
import { LaunchError } from './LaunchError'

export function LiveTests({ launcher, className = '' }: { launcher: LaunchState; className?: string }) {
  return (
    <section className={`live-tests ${className}`} aria-label="Three live tests">
      <p className="live-tests__title">Three live tests in our demo</p>
      <ol className="live-tests__list">
        {LIVE_TESTS.map((t) => (
          <li key={t.tag} className="live-test">
            <p className="live-test__quote">{t.quote}</p>
            <span className={`badge badge--solid-${t.tone} live-test__badge`}>{t.tag}</span>
            <p className="live-test__text">{t.text}</p>
            <button type="button" className="live-test__run" disabled={launcher.busy !== null} aria-busy={launcher.busy === t.tag} onClick={() => void launcher.launch(t.tag, LAUNCHES[t.launch])}>
              {launcher.busy === t.tag ? 'Loading…' : 'Run it'}
              <Icon name="arrow" size={14} />
            </button>
          </li>
        ))}
      </ol>
      <LaunchError launcher={launcher} keys={LIVE_TESTS.map((t) => t.tag)} />
    </section>
  )
}

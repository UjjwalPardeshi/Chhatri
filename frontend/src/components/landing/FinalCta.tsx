/**
 * The end of the landing page: a call to watch it happen (three launchers), the team, and link columns into the
 * console's own pages.
 */
import { Link } from 'react-router'

import { TEAM } from '../../content/deck'
import type { LaunchState } from '../../state/useLaunch'
import { Icon } from '../common/Icon'
import { LaunchButton } from '../overview/LaunchButton'
import { LaunchError } from '../overview/LaunchError'
import { FOOTER_LINKS } from './content'

export const CLOSING_KEYS = ['end-storm', 'end-phone', 'end-case'] as const

export function FinalCta({ launcher }: { launcher: LaunchState }) {
  return (
    <section className="lp-cta" aria-label="See it live">
      <div className="lp-cta__inner">
        <h2 className="lp-cta__title">See the claim start itself.</h2>
        <p className="lp-cta__text">Everything above runs in this browser: the storm, the phone, the claims console and the audit log.</p>
        <div className="lp-cta__buttons">
          <LaunchButton launcher={launcher} id="end-storm" target="stormLive" label="Watch the storm replay" busyLabel="Loading the storm…" />
          <LaunchButton launcher={launcher} id="end-phone" target="questions" tone="ghost" label="See Anil’s phone" busyLabel="Opening the phone…" />
          <LaunchButton launcher={launcher} id="end-case" target="reviewCase" tone="ghost" label="Review the slip mismatch" busyLabel="Opening the case…" />
        </div>
        <LaunchError launcher={launcher} keys={CLOSING_KEYS} />
      </div>
    </section>
  )
}

export function LandingFooter() {
  return (
    <footer className="lp-footer" aria-label="About Chhatri">
      <div className="lp-footer__inner">
        <div className="lp-footer__brand">
          <p className="lp-footer__logo">
            <Icon name="umbrella" size={20} />
            Chhatri{' '}
            <span lang="hi" className="hi">
              छतरी
            </span>
          </p>
          <p className="lp-footer__text">
            Built by {TEAM.name} ({TEAM.members.join(' and ')}) for the Paytm Build for India AI Hackathon, Mumbai. A prototype on simulated data, not an insurance offer.
          </p>
        </div>
        {FOOTER_LINKS.map((column) => (
          <nav key={column.title} className="lp-footer__col" aria-label={column.title}>
            <p className="lp-footer__title">{column.title}</p>
            <ul>
              {column.links.map((link) => (
                <li key={link.to}>
                  <Link to={link.to}>{link.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
    </footer>
  )
}

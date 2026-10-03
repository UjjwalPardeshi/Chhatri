/**
 * Landing hero: the promise in one line, two ways into the live demo and a quiet third into the claims console, three
 * promises with ticks, and the product itself: Anil's phone on the storm evening with two cards from the same replay
 * (the area's sales and the paused instalment) floating beside it.
 */
import { HERO_THREAD, RAIN_SOUNDBOX, STORY } from '../../content/story'
import type { LaunchState } from '../../state/useLaunch'
import { Icon } from '../common/Icon'
import { LaunchButton } from '../overview/LaunchButton'
import { LaunchError } from '../overview/LaunchError'
import { StoryPhone } from '../overview/StoryPhone'
import { PROMISES } from './content'

const HERO_NOW = '2025-08-19T17:06:00+05:30'
export const HERO_LAUNCH_KEYS = ['hero-storm', 'hero-phone', 'hero-case'] as const

export function LandingHero({ launcher }: { launcher: LaunchState }) {
  return (
    <section className="lp-hero" id="top" aria-label="Chhatri">
      <div className="lp-hero__inner">
        <div className="lp-hero__copy">
          <p className="lp-pill">
            <span className="lp-pill__dot" aria-hidden="true" />
            Chhatri · income cover for Paytm merchants
          </p>
          <h1 className="lp-hero__title">The claim starts itself.</h1>
          <p className="lp-hero__sub">
            When heavy rain or illness stops a shop’s sales, Paytm’s own payments data already shows the loss. Chhatri pays the same day, with no claim form, and asks the lender to pause that day’s loan instalment.
          </p>
          <div className="lp-hero__ctas">
            <LaunchButton launcher={launcher} id="hero-storm" target="stormLive" label="Watch the storm replay" busyLabel="Loading the storm…" />
            <LaunchButton launcher={launcher} id="hero-phone" target="questions" tone="quiet" label="See Anil’s phone" busyLabel="Opening the phone…" />
            <LaunchButton launcher={launcher} id="hero-case" target="reviewCase" tone="link" label="Open the claims console" busyLabel="Opening the case…" />
          </div>
          <LaunchError launcher={launcher} keys={HERO_LAUNCH_KEYS} />
          <ul className="lp-promises">
            {PROMISES.map((promise) => (
              <li key={promise}>
                <span className="lp-promises__tick" aria-hidden="true">
                  <Icon name="check" size={14} />
                </span>
                {promise}
              </li>
            ))}
          </ul>
        </div>
        <div className="lp-hero__visual">
          <StoryPhone className="ov-hero__phone lp-hero__phone" now={HERO_NOW} thread={HERO_THREAD} soundbox={RAIN_SOUNDBOX} />
          <div className="lp-float lp-float--area" aria-hidden="true">
            <span className="lp-float__label">Parel · Lalbaug · 46 shops</span>
            <strong className="lp-float__value num">37% of expected</strong>
            <span className="lp-float__meta">for 3 hours · trigger at 17:00</span>
          </div>
          <div className="lp-float lp-float--edi" aria-hidden="true">
            <span className="lp-float__icon">
              <Icon name="pause" size={14} />
            </span>
            <span>
              <strong className="lp-float__value num">{STORY.instalment} instalment</strong>
              <span className="lp-float__meta">tomorrow · paused at 17:05</span>
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

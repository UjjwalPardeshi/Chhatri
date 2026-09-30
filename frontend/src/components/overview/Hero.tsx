/**
 * Overview hero (deck slide 1): the name, the one-line idea, two launchers into the live demo, the
 * 10-second takeaway (SPEC §17.2 golden numbers) and Anil's phone with the Soundbox line.
 */
import { HERO_FIGURES } from '../../content/deck'
import { HERO_THREAD, RAIN_SOUNDBOX } from '../../content/story'
import type { LaunchState } from '../../state/useLaunch'
import { LaunchButton } from './LaunchButton'
import { LaunchError } from './LaunchError'
import { StoryPhone } from './StoryPhone'

const HERO_NOW = '2025-08-19T17:06:00+05:30'
export const HERO_LAUNCH_KEYS = ['hero-storm', 'hero-phone'] as const

export function Hero({ launcher }: { launcher: LaunchState }) {
  return (
    <section className="ov-hero" aria-label="Chhatri">
      <div className="ov-hero__inner">
        <div className="ov-hero__copy">
          <p className="ov-kicker">Build for India AI Hackathon · Track 2: AI-powered financial journeys</p>
          <h1 className="ov-hero__name">
            Chhatri{' '}
            <span className="ov-hero__gloss">
              <span className="hi" lang="hi">
                छतरी
              </span>{' '}
              · umbrella
            </span>
          </h1>
          <p className="ov-hero__claim">Merchant insurance where the claim starts itself</p>
          <p className="ov-hero__sub">
            Paytm already sees when a shop’s income stops. Chhatri pays the same day, with no claim form, and pauses that day’s loan instalment.
          </p>
          <div className="ov-hero__ctas">
            <LaunchButton launcher={launcher} id="hero-storm" target="stormLive" label="Watch the storm replay" busyLabel="Loading the storm…" />
            <LaunchButton launcher={launcher} id="hero-phone" target="questions" tone="ghost" label="See Anil’s WhatsApp" busyLabel="Opening the phone…" />
          </div>
          <LaunchError launcher={launcher} keys={HERO_LAUNCH_KEYS} />
          <dl className="ov-figures" aria-label="The storm replay in numbers">
            {HERO_FIGURES.map((f) => (
              <div key={f.label} className="ov-figure">
                <dt>{f.label}</dt>
                <dd className="num">{f.value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <StoryPhone className="ov-hero__phone" now={HERO_NOW} thread={HERO_THREAD} soundbox={RAIN_SOUNDBOX} />
      </div>
    </section>
  )
}

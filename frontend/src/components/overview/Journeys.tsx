/**
 * WhatsApp journeys (deck slide 7): rain day, illness, questions, each playable live. On phones the
 * three phones sit in a swipeable row, one at a time.
 */
import type { LaunchKey } from '../../content/deck'
import { JOURNEYS, type Journey } from '../../content/story'
import type { LaunchState } from '../../state/useLaunch'
import { LaunchButton } from './LaunchButton'
import { LaunchError } from './LaunchError'
import { RevealSection } from './Reveal'
import { StoryPhone } from './StoryPhone'

export const JOURNEY_LAUNCH: Readonly<Record<Journey['key'], { target: LaunchKey; label: string; hint: string | null }>> = Object.freeze({
  rain: { target: 'rainDay', label: 'Play the rain day', hint: null },
  illness: { target: 'illness', label: 'Play the illness claim', hint: 'Then tap the voice reply and send the slip.' },
  questions: { target: 'questions', label: 'Ask why ₹1,380', hint: null },
})

export function Journeys({ launcher }: { launcher: LaunchState }) {
  return (
    <RevealSection label="What the merchant sees" className="ov-journeys">
      <h2 className="ov-h2">The merchant gets it on WhatsApp, in Hindi and English.</h2>
      <div className="journeys">
        {JOURNEYS.map((journey, i) => {
          const go = JOURNEY_LAUNCH[journey.key]
          return (
            <article key={journey.key} className="journey" aria-label={journey.title}>
              <header className="journey__head">
                <span className="journey__n num">{i + 1}</span>
                <strong>{journey.title}</strong>
                <span className="muted">{journey.subtitle}</span>
              </header>
              <StoryPhone className="journey__phone" now={journey.now} thread={journey.thread} soundbox={journey.soundbox} />
              <div className="journey__go">
                <LaunchButton launcher={launcher} id={journey.key} target={go.target} tone="quiet" label={go.label} />
                {go.hint ? <p className="journey__hint">{go.hint}</p> : null}
              </div>
            </article>
          )
        })}
      </div>
      <LaunchError launcher={launcher} keys={JOURNEYS.map((j) => j.key)} />
      <p className="ov-source">Every message also plays as a voice note (Sarvam Bulbul); spoken replies are understood by Sarvam Saaras. Demo data.</p>
    </RevealSection>
  )
}

/**
 * How it works: Detect, Decide, Pay, Protect as four numbered cards, then the two ways a claim starts (an area shock
 * the merchant does nothing for, and a personal shock that needs one reply and one photo).
 */
import { Icon } from '../common/Icon'
import { RevealSection } from '../overview/Reveal'
import { STARTS, STEPS } from './content'
import { SectionHead } from './SectionHead'

export function HowSteps() {
  return (
    <RevealSection label="How it works" id="how" className="lp-section">
      <SectionHead eyebrow="How it works" title="Detect. Decide. Pay. Protect." lead="Four steps, all inside the Paytm stack the merchant already uses. The merchant’s only job on a bad day is to answer if asked." />
      <ol className="lp-steps">
        {STEPS.map((step, i) => (
          <li key={step.title} className={`lp-step ${step.title === 'Decide' ? 'lp-step--rules' : ''}`}>
            <span className="lp-step__icon" aria-hidden="true">
              <Icon name={step.icon} size={20} />
            </span>
            <span className="lp-step__n num">0{i + 1}</span>
            <h3 className="lp-step__title">{step.title}</h3>
            <p className="lp-step__text">{step.text}</p>
          </li>
        ))}
      </ol>
      <div className="lp-starts">
        {STARTS.map((start) => (
          <article key={start.title} className="lp-start" aria-label={start.title}>
            <h3 className="lp-start__title">{start.title}</h3>
            <dl>
              <div>
                <dt>Starts when</dt>
                <dd>{start.when}</dd>
              </div>
              <div>
                <dt>Merchant does</dt>
                <dd className={start.merchant === 'Nothing' ? 'lp-start__nothing' : ''}>{start.merchant}</dd>
              </div>
              <div>
                <dt>Checked by</dt>
                <dd>{start.check}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </RevealSection>
  )
}

/**
 * Why Paytm: the storm replay told as one journey, each step tagged with the thing it runs on. Four of the six steps
 * run on something only Paytm has (payments data, settlement, Soundbox, merchant loans), so the journey cannot move
 * to another fintech without a step going missing.
 */
import { RevealSection } from '../overview/Reveal'
import { PAYTM_JOURNEY } from './content'
import { SectionHead } from './SectionHead'

export function WhyPaytm() {
  return (
    <RevealSection label="Why Paytm" id="why-paytm" className="lp-section" tone="white">
      <SectionHead
        eyebrow="Why Paytm"
        title="One journey, end to end, on rails Paytm already runs."
        lead="The storm evening of the replay, step by step. The blue steps need something only Paytm has: swap in another fintech and they go missing."
      />
      <ol className="lp-journey">
        {PAYTM_JOURNEY.map((step) => (
          <li key={`${step.at}-${step.asset}`} className={`lp-journey__step ${step.paytm ? 'lp-journey__step--paytm' : ''}`}>
            <time className="lp-journey__at num">{step.at}</time>
            <span className="lp-journey__dot" aria-hidden="true" />
            <span className="lp-journey__text">{step.text}</span>
            <span className="lp-journey__asset">{step.asset}</span>
          </li>
        ))}
      </ol>
      <p className="ov-source">Monsoon replay of 19 Aug 2025. Sales, the settlement, the Soundbox and the lender are simulated.</p>
    </RevealSection>
  )
}

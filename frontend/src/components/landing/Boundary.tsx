/**
 * "AI understands. Rules decide. Paytm executes." Three lanes left to right, with a red boundary between the AI lane
 * and the rules lane: whatever the AI says, only the policy engine can approve money (SPEC §9.4, ADR 0003).
 */
import { Icon } from '../common/Icon'
import { RevealSection } from '../overview/Reveal'
import { BOUNDARY_LABEL, LANES } from './content'
import { SectionHead } from './SectionHead'

export function Boundary() {
  return (
    <RevealSection label="Who decides" id="boundary" className="lp-section lp-boundary" tone="navy">
      <SectionHead
        eyebrow="Who decides"
        title="AI understands. Rules decide. Paytm executes."
        lead="AI is allowed to be unsure. It is never allowed to move money: a payout needs the policy engine, and an unclear case goes to a person."
      />
      <div className="lp-lanes">
        {LANES.map((lane) => (
          <article key={lane.key} className={`lp-lane lp-lane--${lane.key}`} aria-label={lane.verb}>
            <p className="lp-lane__verb">{lane.verb}</p>
            <h3 className="lp-lane__title">{lane.title}</h3>
            <ul className="lp-lane__items">
              {lane.items.map((item) => (
                <li key={item}>
                  <Icon name="check" size={14} />
                  {item}
                </li>
              ))}
            </ul>
            <p className="lp-lane__note">{lane.note}</p>
            {lane.key === 'ai' ? (
              <p className="lp-wall" role="note">
                <span>{BOUNDARY_LABEL}</span>
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </RevealSection>
  )
}

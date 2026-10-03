/** What the product does for a merchant, as a grid of eight cards (icon, title, one sentence). */
import { Icon } from '../common/Icon'
import { RevealSection } from '../overview/Reveal'
import { FEATURES } from './content'
import { SectionHead } from './SectionHead'

export function Features() {
  return (
    <RevealSection label="Features" id="features" className="lp-section">
      <SectionHead eyebrow="Product" title="Everything a merchant needs on a bad day, and nothing to fill in." center />
      <ul className="lp-features">
        {FEATURES.map((feature) => (
          <li key={feature.title} className="lp-feature">
            <span className="lp-feature__icon" aria-hidden="true">
              {feature.icon ? <Icon name={feature.icon} size={20} /> : <span className="lp-feature__glyph">{feature.glyph}</span>}
            </span>
            <h3 className="lp-feature__title">{feature.title}</h3>
            <p className="lp-feature__text">{feature.text}</p>
          </li>
        ))}
      </ul>
    </RevealSection>
  )
}

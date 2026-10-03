/** Questions a merchant, an insurer or a judge asks first, as native disclosure widgets (keyboard and reader friendly). */
import { RevealSection } from '../overview/Reveal'
import { FAQS } from './content'
import { SectionHead } from './SectionHead'

export function Faq() {
  return (
    <RevealSection label="Questions" id="faq" className="lp-section" tone="white">
      <SectionHead eyebrow="FAQ" title="Questions people ask first." center />
      <div className="lp-faq">
        {FAQS.map((item) => (
          <details key={item.q} className="lp-faq__item">
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
    </RevealSection>
  )
}

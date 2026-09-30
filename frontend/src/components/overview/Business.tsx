/**
 * Why Paytm wins (deck slide 12): financial services revenue (₹ crore, Q1 FY26 → Q1 FY27), the
 * four value drivers and the go-to-market, then who benefits (deck slide 11), with the deck's
 * sources.
 */
import { BUSINESS } from '../../content/deck'
import { BENEFITS } from '../../content/deckValue'
import { RevealSection } from './Reveal'

const MAX_CRORE = Math.max(...BUSINESS.revenue.map((r) => r.crore))

function RevenueBars() {
  return (
    <figure className="revenue" aria-label={BUSINESS.chartLabel}>
      <figcaption className="ov-label">{BUSINESS.chartLabel}</figcaption>
      <div className="revenue__plot">
        {BUSINESS.revenue.map((r) => (
          <div key={r.quarter} className={`revenue__col ${r.ours ? 'revenue__col--now' : ''}`}>
            <span className="revenue__value num">{r.crore}</span>
            <span className="revenue__bar" style={{ height: `${(r.crore / MAX_CRORE) * 100}%` }} />
            <span className="revenue__quarter">{r.quarter}</span>
          </div>
        ))}
      </div>
      <p className="revenue__note">
        <strong>{BUSINESS.growth}</strong> {BUSINESS.growthNote}
      </p>
    </figure>
  )
}

export function Business() {
  return (
    <RevealSection label="Why Paytm" id="ov-business" className="ov-business">
      <h2 className="ov-h2">{BUSINESS.title}</h2>
      <div className="ov-business__grid">
        <RevenueBars />
        <div>
          <p className="ov-label">Where the value comes from</p>
          <dl className="drivers">
            {BUSINESS.drivers.map((d) => (
              <div key={d.driver} className="drivers__row">
                <dt>{d.driver}</dt>
                <dd>{d.how}</dd>
              </div>
            ))}
          </dl>
          <p className="gtm">
            <span className="gtm__label">Go-to-market</span>
            {BUSINESS.goToMarket}
          </p>
        </div>
      </div>
      <section className="benefits" aria-label="Who benefits">
        <p className="ov-label">Who benefits</p>
        <div className="benefits__grid">
          {BENEFITS.map((b) => (
            <article key={b.who} className="benefit">
              <h3 className="benefit__who">{b.who}</h3>
              <p className="benefit__what">{b.what}</p>
            </article>
          ))}
        </div>
      </section>
      <p className="ov-source">{BUSINESS.sources}</p>
    </RevealSection>
  )
}

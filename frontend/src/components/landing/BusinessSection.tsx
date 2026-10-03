/**
 * Who gains and what it costs: one row per party (merchant, insurer, Paytm, lender), marked as what a pilot would
 * test, and the backtest price range beside the open question it leaves (SPEC business model §3). With the flag
 * h24_whatif the price links to the pricing simulator at the end of the Backtest page.
 */
import { Link } from 'react-router'

import { isFeatureEnabled } from '../../features'
import { Icon } from '../common/Icon'
import { RevealSection } from '../overview/Reveal'
import { PARTIES, PARTIES_NOTE, PRICE } from './content'
import { SectionHead } from './SectionHead'

export function BusinessSection() {
  return (
    <RevealSection label="Who gains" id="business" className="lp-section" tone="white">
      <SectionHead eyebrow="Business" title="Good for the merchant, the insurer, Paytm and the lender." />
      <div className="lp-business">
        <table className="lp-parties">
          <thead>
            <tr>
              <th scope="col">Who</th>
              <th scope="col">What they get</th>
              <th scope="col">How it shows up</th>
            </tr>
          </thead>
          <tbody>
            {PARTIES.map((row) => (
              <tr key={row.party}>
                <th scope="row">{row.party}</th>
                <td>{row.gets}</td>
                <td>{row.shows}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <aside className="lp-price" aria-label="What it costs">
          <p className="lp-price__label">What it costs a merchant</p>
          <p className="lp-price__value num">{PRICE.range}</p>
          <p className="lp-price__unit">a day, by zone</p>
          <p className="lp-price__example num">{PRICE.example}</p>
          <p className="lp-price__note">{PRICE.note}</p>
          {isFeatureEnabled('h24_whatif') ? (
            <Link className="lp-price__link" to="/backtest#pricing">
              Try the pricing simulator <Icon name="arrow" size={16} />
            </Link>
          ) : null}
        </aside>
      </div>
      <p className="ov-source">{PARTIES_NOTE}</p>
    </RevealSection>
  )
}

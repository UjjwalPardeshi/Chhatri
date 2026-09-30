/**
 * How it works (deck slides 4 and 5): one engine in five steps with the learning loop drawn from
 * step 5 back to step 1, and the two ways a claim starts itself (a table, or two cards on phones).
 */
import type { CSSProperties } from 'react'

import { ENGINE_STEPS, LEARN_LOOP, TWO_WAYS } from '../../content/deck'
import { Icon } from '../common/Icon'
import { RevealSection } from './Reveal'

const AREA_TITLE = 'Area shock · rain, heatwave, bandh'
const PERSONAL_TITLE = 'Personal shock · illness, accident'

function Engine() {
  return (
    <div className="engine-wrap">
      <ol className="engine">
        {ENGINE_STEPS.map((step, i) => (
          <li key={step.title} className={`engine__step ${step.control ? 'engine__step--control' : ''}`} style={{ '--i': i } as CSSProperties}>
            <span className="engine__n num">{i + 1}</span>
            <strong className="engine__title">{step.title}</strong>
            <span className="engine__text">{step.text}</span>
            {i < ENGINE_STEPS.length - 1 ? (
              <span className="engine__arrow" aria-hidden="true">
                <Icon name="arrow" size={16} />
              </span>
            ) : null}
          </li>
        ))}
      </ol>
      <div className="engine__loop">
        <span className="engine__loop-line" aria-hidden="true">
          <span className="engine__loop-head" />
        </span>
        <p className="engine__loop-text">{LEARN_LOOP}</p>
      </div>
    </div>
  )
}

function TwoWaysCards() {
  const columns = [
    { title: AREA_TITLE, pick: (row: (typeof TWO_WAYS)[number]) => row.area },
    { title: PERSONAL_TITLE, pick: (row: (typeof TWO_WAYS)[number]) => row.personal },
  ]
  return (
    <div className="two-ways-cards">
      {columns.map((column) => (
        <article key={column.title} className="two-ways-card" aria-label={column.title}>
          <h3>{column.title}</h3>
          <dl>
            {TWO_WAYS.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{column.pick(row)}</dd>
              </div>
            ))}
          </dl>
        </article>
      ))}
    </div>
  )
}

export function HowItWorks() {
  return (
    <RevealSection label="How it works" className="ov-how">
      <h2 className="ov-h2">One engine, two ways a claim starts itself.</h2>
      <Engine />
      <table className="two-ways">
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Question</span>
            </th>
            <th scope="col">{AREA_TITLE}</th>
            <th scope="col">{PERSONAL_TITLE}</th>
          </tr>
        </thead>
        <tbody>
          {TWO_WAYS.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td className={row.area === 'Nothing' ? 'two-ways__strong' : ''}>{row.area}</td>
              <td>{row.personal}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <TwoWaysCards />
      <p className="ov-lede">
        The AI builds the case. <strong>Code checks every payout against the policy</strong> before any money moves, and every step is logged.
      </p>
    </RevealSection>
  )
}

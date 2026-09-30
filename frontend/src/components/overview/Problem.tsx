/**
 * The problem (deck slides 2 and 3): how long money takes after a loss today, why merchant
 * insurance keeps failing, and one bad day told two ways.
 */
import { CHHATRI_DAY, FAILURES, PROBLEM_SOURCES, TIME_TO_MONEY, TYPICAL_DAY, type TimelineStep, type TimeToMoney } from '../../content/deck'
import { RevealSection } from './Reveal'

/** Longest wait on the chart (days); bar lengths are relative to it. */
export const CHART_MAX_DAYS = Math.max(...TIME_TO_MONEY.map((t) => t.maxDays))

/** Bar geometry in % of the track: the range [min, max] days, drawn from 0 like the deck. */
export function barWidthPct(row: TimeToMoney): number {
  return (row.maxDays / CHART_MAX_DAYS) * 100
}

function WaitChart() {
  return (
    <figure className="wait-chart" aria-label="Time to money after a loss, in days">
      <figcaption className="ov-label">Time to money after a loss, in days</figcaption>
      {TIME_TO_MONEY.map((row) => (
        <div key={row.label} className={`wait-row ${row.ours ? 'wait-row--ours' : ''}`}>
          <span className="wait-row__label">{row.label}</span>
          <span className="wait-row__track">
            {row.ours ? <span className="wait-row__dot" aria-hidden="true" /> : <span className="wait-row__bar" style={{ width: `${barWidthPct(row)}%` }} />}
          </span>
          <span className="wait-row__value num">{row.text}</span>
        </div>
      ))}
      <p className="wait-chart__note">Earlier plans also needed multiple documents, and outcomes were uncertain, so merchants stopped trusting the category.</p>
    </figure>
  )
}

export function Problem() {
  return (
    <RevealSection label="The problem" className="ov-problem">
      <h2 className="ov-h2">A bad day costs a shop its income. Getting paid for it takes weeks, if it happens at all.</h2>
      <div className="ov-problem__grid">
        <WaitChart />
        <div className="failures">
          <p className="ov-label">Why merchant insurance keeps failing</p>
          <dl className="failures__list">
            {FAILURES.map((f) => (
              <div key={f.what} className="failures__item">
                <dt>{f.what}</dt>
                <dd>{f.evidence}</dd>
              </div>
            ))}
          </dl>
          <p className="failures__fix">
            The fix is already inside Paytm: it sees every shop’s sales live, across <strong>1.57 crore device merchants</strong>. It can <strong>measure the loss instead of guessing it</strong>.
          </p>
        </div>
      </div>
      <p className="ov-source">{PROBLEM_SOURCES}</p>
    </RevealSection>
  )
}

function Timeline({ steps, tone, title, result, detail }: { steps: readonly TimelineStep[]; tone: 'typical' | 'chhatri'; title: string; result: string; detail: string }) {
  return (
    <article className={`day-card day-card--${tone}`} aria-label={title}>
      <h3 className="day-card__title">{title}</h3>
      <ol className="day-card__steps">
        {steps.map((s) => (
          <li key={s.at}>
            <time className="day-card__at num">{s.at}</time>
            <span>{s.text}</span>
          </li>
        ))}
      </ol>
      <p className="day-card__result">
        <strong>{result}</strong> <span>{detail}</span>
      </p>
    </article>
  )
}

export function BadDay() {
  return (
    <RevealSection label="One bad day" className="ov-badday" tone="white">
      <h2 className="ov-h2">A rainy day today means weeks of paperwork. With Chhatri, it’s paid that evening.</h2>
      <div className="ov-badday__grid">
        <Timeline steps={TYPICAL_DAY} tone="typical" title="Typical today" result="Paid in 30-60 days" detail="Forms and documents, outcome uncertain" />
        <Timeline steps={CHHATRI_DAY} tone="chhatri" title="With Chhatri" result="Paid the same day" detail="0 forms, 0 documents" />
      </div>
      <p className="ov-lede">
        Paytm’s merchant plan already fixed price and sign-up: under ₹2 a day, three taps in the app. Chhatri fixes the part that broke trust before: <strong>the claim</strong>.
      </p>
    </RevealSection>
  )
}

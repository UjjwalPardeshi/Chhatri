/**
 * The problem as a before and after (deck slides 2 and 3): one bad day today, with forms and a 30–60 day wait, beside
 * the same day with Chhatri, and the three reasons merchant insurance keeps failing, with their sources.
 */
import { CHHATRI_DAY, FAILURES, PROBLEM_SOURCES, TYPICAL_DAY, type TimelineStep } from '../../content/deck'
import { RevealSection } from '../overview/Reveal'
import { SectionHead } from './SectionHead'

type DayProps = { tone: 'before' | 'after'; title: string; steps: readonly TimelineStep[]; result: string; detail: string }

function Day({ tone, title, steps, result, detail }: DayProps) {
  return (
    <article className={`lp-day lp-day--${tone}`} aria-label={title}>
      <h3 className="lp-day__title">{title}</h3>
      <ol className="lp-day__steps">
        {steps.map((step) => (
          <li key={step.at}>
            <time className="lp-day__at num">{step.at}</time>
            <span>{step.text}</span>
          </li>
        ))}
      </ol>
      <p className="lp-day__result">
        <strong className="num">{result}</strong>
        <span>{detail}</span>
      </p>
    </article>
  )
}

export function BeforeAfter() {
  return (
    <RevealSection label="The problem" id="problem" className="lp-section" tone="white">
      <SectionHead
        eyebrow="The problem"
        title="A merchant shouldn’t have to file a claim for Paytm to know a shock just happened."
        lead="Paytm already sees every shop’s sales. Today a bad day still means a form, documents and weeks of waiting, and the loan instalment is cut anyway."
      />
      <div className="lp-days">
        <Day tone="before" title="Today" steps={TYPICAL_DAY} result="30-60 days" detail="Forms and documents, outcome uncertain" />
        <Day tone="after" title="With Chhatri" steps={CHHATRI_DAY} result="Same day" detail="0 forms, 0 documents" />
      </div>
      <ul className="lp-fails" aria-label="Why merchant insurance keeps failing">
        {FAILURES.map((failure) => (
          <li key={failure.what}>
            <strong>{failure.what}</strong>
            <span>{failure.evidence}</span>
          </li>
        ))}
      </ul>
      <p className="ov-source">{PROBLEM_SOURCES}</p>
    </RevealSection>
  )
}

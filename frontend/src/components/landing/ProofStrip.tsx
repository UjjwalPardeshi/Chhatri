/** The figures under the hero: the monsoon replay in four numbers, captioned as a replay (SPEC §17.2). */
import { CountUp } from '../overview/CountUp'
import { REPLAY_CAPTION, REPLAY_FIGURES } from './content'

export function ProofStrip() {
  return (
    <section className="lp-strip" aria-label="The storm replay in numbers">
      <div className="lp-strip__inner">
        <dl className="lp-strip__figures">
          {REPLAY_FIGURES.map((figure) => (
            <div key={figure.label} className="lp-strip__figure">
              <dt>{figure.label}</dt>
              <dd className="num">{figure.count ? <CountUp value={figure.value} /> : figure.value}</dd>
            </div>
          ))}
        </dl>
        <p className="lp-strip__caption">{REPLAY_CAPTION}</p>
      </div>
    </section>
  )
}

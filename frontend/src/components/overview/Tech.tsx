/**
 * Technology (deck slide 9), then what is real, keyed or simulated (SPEC §0.1) with the live count
 * from GET /api/integrations and each integration's mode folded under a button (Honesty.tsx;
 * nothing simulated is presented as live).
 */
import { ACTIONS, CONTROL, REASONING, SIGNALS, STACK } from '../../content/deck'
import { LiveNow, Tiers } from './Honesty'
import { RevealSection } from './Reveal'

export function Tech() {
  return (
    <RevealSection label="Technology" id="ov-tech" className="ov-tech" tone="white">
      <h2 className="ov-h2">Statistics measure the loss, AI talks to people, code controls the money.</h2>
      <div className="tech">
        <div className="tech__col">
          <p className="tech__head">Signals</p>
          <ul className="tech__signals">
            {SIGNALS.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="tech__col">
          <p className="tech__head">Reasoning + memory</p>
          {REASONING.map((r) => (
            <div key={r.title} className="tech__card">
              <strong>{r.title}</strong>
              <span>{r.text}</span>
            </div>
          ))}
        </div>
        <div className="tech__col">
          <p className="tech__head">Control</p>
          <div className="tech__control">
            <strong>Policy engine</strong>
            {CONTROL.slice(0, 2).map((c) => (
              <span key={c}>{c}</span>
            ))}
            <span className="tech__only">The only layer that can approve a payout</span>
            <span>{CONTROL[2]}</span>
          </div>
        </div>
        <div className="tech__col">
          <p className="tech__head">Action</p>
          {ACTIONS.map((a) => (
            <div key={a.title} className="tech__card">
              <strong>{a.title}</strong>
              <span>{a.text}</span>
            </div>
          ))}
        </div>
      </div>
      <ul className="stack" aria-label="Stack">
        {STACK.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
      <Tiers />
      <LiveNow />
    </RevealSection>
  )
}

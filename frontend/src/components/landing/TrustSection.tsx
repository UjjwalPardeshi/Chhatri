/**
 * What is real and what is simulated (SPEC §0.1): the three tiers and the live integration list (read from
 * GET /api/integrations), then a way into each page that lets a reader check a claim for themselves.
 */
import { Link } from 'react-router'

import { isFeatureEnabled } from '../../features'
import { Icon, type IconName } from '../common/Icon'
import { LiveNow, Tiers } from '../overview/Honesty'
import { RevealSection } from '../overview/Reveal'
import { SectionHead } from './SectionHead'

type Check = { to: string; title: string; text: string; icon: IconName }

const CHECKS: readonly Check[] = [
  { to: '/audit', title: 'Audit log', text: 'Every decision, credit and pause, hash-chained. Verify it in one click.', icon: 'shield' },
  { to: '/backtest', title: 'Backtest', text: 'Two past monsoons replayed: real rainfall, simulated sales.', icon: 'drop' },
  { to: '/policy', title: 'Policy wording', text: 'The twelve clauses every answer and decision cites.', icon: 'notes' },
]
const EVALS: Check = { to: '/evals', title: 'AI evaluation', text: 'How often the AI routes, refuses and answers correctly, k of n.', icon: 'question' }

export function TrustSection() {
  const checks = isFeatureEnabled('h25_evals') ? [...CHECKS, EVALS] : CHECKS
  return (
    <RevealSection label="What is real" id="trust" className="lp-section lp-trust">
      <SectionHead eyebrow="Honesty" title="What is real, and what is simulated." lead="Nothing simulated is dressed up as live. Every screen in the demo says which is which." />
      <Tiers />
      <LiveNow />
      <ul className="lp-checks">
        {checks.map((check) => (
          <li key={check.to}>
            <Link className="lp-check" to={check.to}>
              <span className="lp-check__icon" aria-hidden="true">
                <Icon name={check.icon} size={18} />
              </span>
              <span>
                <strong>{check.title}</strong>
                <span className="lp-check__text">{check.text}</span>
              </span>
              <Icon name="arrow" size={16} />
            </Link>
          </li>
        ))}
      </ul>
    </RevealSection>
  )
}

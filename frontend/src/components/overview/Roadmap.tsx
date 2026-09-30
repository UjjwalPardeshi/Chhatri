/**
 * Roadmap and team (deck slide 13) with three honest tiers of what is real, what can be live and
 * what is always simulated (SPEC §0.1); the live count is read from GET /api/integrations.
 */
import { HONESTY_TIERS, ROADMAP, TEAM } from '../../content/deck'
import { useLive } from '../../state/live'
import { integrationCounts } from '../layout/IntegrationBadges'

function LiveCount() {
  const { integrations, integrationsError } = useLive()
  if (integrationsError) return <span className="tier__now">Live status unavailable right now.</span>
  if (!integrations) return <span className="tier__now">Checking what is live…</span>
  const { live, simulated } = integrationCounts(integrations)
  return (
    <span className="tier__now num">
      Right now: {live} live, {simulated} simulated.
    </span>
  )
}

function Tiers() {
  const tiers = [
    { key: 'real', ...HONESTY_TIERS.real, extra: null },
    { key: 'keyed', ...HONESTY_TIERS.keyed, extra: <LiveCount /> },
    { key: 'simulated', ...HONESTY_TIERS.simulated, extra: null },
  ]
  return (
    <div className="tiers" aria-label="What is live in our prototype">
      {tiers.map((tier) => (
        <div key={tier.key} className={`tier tier--${tier.key}`}>
          <p className="tier__title">{tier.title}</p>
          <p className="tier__text">
            {tier.text} {tier.extra}
          </p>
        </div>
      ))}
    </div>
  )
}

export function Roadmap() {
  return (
    <section className="ov-roadmap" aria-label="Roadmap and team">
      <div className="ov-roadmap__inner">
        <h2 className="ov-h2 ov-h2--light">A working prototype by 3 October, then a monsoon pilot.</h2>
        <div className="roadmap">
          {ROADMAP.map((phase) => (
            <article key={phase.title} className="roadmap__card">
              <p className="roadmap__when">{phase.when}</p>
              <h3>{phase.title}</h3>
              <ul>
                {phase.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <Tiers />
        <div className="team">
          <div>
            <p className="team__label">Team</p>
            <p className="team__name">{TEAM.name}</p>
          </div>
          {TEAM.members.map((member) => (
            <div key={member}>
              <p className="team__member">{member}</p>
              <p className="team__role">{TEAM.role}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

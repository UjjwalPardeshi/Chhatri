/**
 * Roadmap and team (deck slide 13). What is live in the prototype sits with the technology
 * (Honesty.tsx), so this band is only the plan and the people.
 */
import { ROADMAP, TEAM } from '../../content/deck'

export function Roadmap() {
  return (
    <section className="ov-roadmap" id="ov-roadmap" aria-label="Roadmap and team">
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

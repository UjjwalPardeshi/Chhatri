/**
 * Overview homepage "/" (SPEC §20 routes; B10): the whole idea told like the deck, from the
 * problem to the team, with launchers into the live demo (live map, phone, claims, backtest) and a
 * sticky section rail under the hero.
 * Surfaces alternate (navy hero, paper, white, navy storm, ...) so the long page keeps a rhythm.
 */
import { Business } from '../components/overview/Business'
import { Closing } from '../components/overview/Closing'
import { Hero } from '../components/overview/Hero'
import { HowItWorks } from '../components/overview/HowItWorks'
import { Humans } from '../components/overview/Humans'
import { Journeys } from '../components/overview/Journeys'
import { BadDay, Problem } from '../components/overview/Problem'
import { Proof } from '../components/overview/Proof'
import { Roadmap } from '../components/overview/Roadmap'
import { SectionRail } from '../components/overview/SectionRail'
import { Storm } from '../components/overview/Storm'
import { Tech } from '../components/overview/Tech'
import { Usp } from '../components/overview/Usp'
import { useLaunch } from '../state/useLaunch'

export default function Overview() {
  const launcher = useLaunch()
  return (
    <div className="overview">
      <Hero launcher={launcher} />
      <SectionRail />
      <Problem />
      <BadDay />
      <HowItWorks />
      <Storm launcher={launcher} />
      <Journeys launcher={launcher} />
      <Humans launcher={launcher} />
      <Proof />
      <Usp />
      <Tech />
      <Business />
      <Roadmap />
      <Closing launcher={launcher} />
    </div>
  )
}

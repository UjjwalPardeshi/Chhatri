/**
 * Landing page "/" (SPEC §20 routes; B10): what Chhatri is, how it works, who decides, why it needs Paytm, the live
 * demo launchers (storm, merchant phones, humans in control), proof, business, honesty and questions, then a call
 * to watch it happen. Surfaces alternate white, paper and navy so the long page keeps a rhythm.
 */
import { BeforeAfter } from '../components/landing/BeforeAfter'
import { Boundary } from '../components/landing/Boundary'
import { BusinessSection } from '../components/landing/BusinessSection'
import { Faq } from '../components/landing/Faq'
import { Features } from '../components/landing/Features'
import { FinalCta, LandingFooter } from '../components/landing/FinalCta'
import { HowSteps } from '../components/landing/HowSteps'
import { LandingHero } from '../components/landing/LandingHero'
import { ProofStrip } from '../components/landing/ProofStrip'
import { TrustSection } from '../components/landing/TrustSection'
import { WhyPaytm } from '../components/landing/WhyPaytm'
import { Humans } from '../components/overview/Humans'
import { Journeys } from '../components/overview/Journeys'
import { Proof } from '../components/overview/Proof'
import { Storm } from '../components/overview/Storm'
import { useLaunch } from '../state/useLaunch'

export default function Overview() {
  const launcher = useLaunch()
  return (
    <div className="overview landing">
      <LandingHero launcher={launcher} />
      <ProofStrip />
      <BeforeAfter />
      <HowSteps />
      <Boundary />
      <WhyPaytm />
      <Storm launcher={launcher} />
      <Journeys launcher={launcher} />
      <Humans launcher={launcher} />
      <Features />
      <Proof />
      <BusinessSection />
      <TrustSection />
      <Faq />
      <FinalCta launcher={launcher} />
      <LandingFooter />
    </div>
  )
}

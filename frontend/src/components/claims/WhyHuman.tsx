/**
 * The red "Why a human" strip under the decision (SPEC §9.4, deck slide 8 "HUMAN"): each check
 * that stopped the automatic payout, in plain words with its numbers (whyHuman.ts). A failed
 * name check shows the two names side by side with the score and a zoom of the slip
 * (NameCompare). The policy engine's own sentence is the strip's tooltip; it is shown only when
 * no check explains the referral.
 */
import type { CaseEvidence, Decision } from '../../api/types'
import { Icon } from '../common/Icon'
import { NameCompare } from './NameCompare'
import { humanReasons, type HumanReason } from './whyHuman'

function Reason({ reason, evidence }: { reason: HumanReason; evidence: CaseEvidence }) {
  const compare = reason.code === 'NAME_MATCHES_KYC' && reason.tone === 'red' && Boolean(evidence.slip?.patient_name && evidence.kyc_name)
  return (
    <li className={`why__item why__item--${reason.tone}`}>
      <span className="why__icon" aria-hidden="true">
        <Icon name={reason.tone === 'red' ? 'cross' : 'question'} size={14} />
      </span>
      <span className="why__body">
        <strong className="why__title">{reason.title}</strong>
        {compare ? <NameCompare evidence={evidence} /> : reason.detail ? <span className="why__detail num">{reason.detail}</span> : null}
      </span>
    </li>
  )
}

export function WhyHuman({ decision, evidence }: { decision: Decision; evidence: CaseEvidence }) {
  if (decision.outcome !== 'REFERRED') return null
  const reasons = humanReasons(decision.checks, evidence)
  return (
    <section className="why" aria-label="Why a human" title={decision.referral_reason ?? undefined}>
      <p className="why__lead">Why a human:</p>
      {reasons.length > 0 ? (
        <ul className="why__list">
          {reasons.map((r) => (
            <Reason key={r.code} reason={r} evidence={evidence} />
          ))}
        </ul>
      ) : decision.referral_reason ? (
        <p className="why__engine">Policy engine: {decision.referral_reason}</p>
      ) : null}
    </section>
  )
}

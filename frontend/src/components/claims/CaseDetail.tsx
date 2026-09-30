/**
 * Case detail (SPEC §9.4, §12, §20 "Claims"): a plain-words headline with the failed rule under
 * it (caseSummary.ts), decision with formula, the red "Why a human" strip, one-tap Approve /
 * Decline with the officer token, evidence and checks. After an officer approval the policy
 * engine's REFERRED decision (`referral`, the one the officer's decision supersedes) still
 * explains why a human decided, and the resolution says when the money reaches the merchant on
 * the replay clock (SPEC §10: credited_at = decided_at + payout_rail_delay_minutes).
 */
import { useState } from 'react'
import { Link } from 'react-router'

import type { ApiError } from '../../api/client'
import type { Case, Decision } from '../../api/types'
import { actorLabel, isOfficer } from '../../lib/actors'
import { dayLabel, hhmm, hhmmAfter, minutesBetween, slaState } from '../../lib/time'
import { InlineError } from '../common/Status'
import { caseHeadline, referralDecision } from './caseSummary'
import { Checks } from './Checks'
import { Evidence } from './Evidence'
import { CASE_KIND_LABELS, CASE_STATUS_TONES, OUTCOME_TONES } from './labels'
import { WhyHuman } from './WhyHuman'

export { actorLabel } from '../../lib/actors'

/** The server's own resolution sentences already name the claims officer (dispute outcomes). */
const SERVER_WORDING = 'claims officer'

/** "Approved by claims officer", the server's dispute outcome as written, or the officer's note with who wrote it. */
export function resolutionText(item: Pick<Case, 'status' | 'resolution' | 'resolved_by'>): string {
  const word = item.status.charAt(0) + item.status.slice(1).toLowerCase()
  const resolution = item.resolution?.trim() ?? ''
  if (!item.resolved_by) return resolution || word
  const by = actorLabel(item.resolved_by)
  if (resolution === '' || resolution === `${word} by ${item.resolved_by}`) return `${word} by ${by}`
  if (resolution.includes(SERVER_WORDING)) return resolution
  return `“${resolution}” · ${by}`
}

export type OfficerAction = (approve: boolean, note: string) => Promise<void>

function DecisionBlock({ decision, title }: { decision: Decision; title: string }) {
  return (
    <div className="decision" data-outcome={decision.outcome}>
      <div className="decision__head">
        <span className="eyebrow">{title}</span>
        <span className={`badge badge--${OUTCOME_TONES[decision.outcome] ?? 'grey'}`}>{decision.outcome}</span>
        <strong className="decision__amount num">{decision.amount_label}</strong>
        <span className="muted num">
          {decision.id} · {actorLabel(decision.decided_by)} · {hhmm(decision.decided_at)}
          {decision.supersedes ? ` · supersedes ${decision.supersedes}` : ''}
        </span>
      </div>
      {decision.explanation ? <p className="decision__formula num">{decision.explanation.formula_en}</p> : null}
    </div>
  )
}

/**
 * "₹1,500 credited to Anil's Tea Stall at 11:29, with the settlement." once the replay clock has
 * passed the credit time (SPEC §10), "reaches … at 11:29 on the replay clock" before it.
 */
export function creditNote(item: Pick<Case, 'decision' | 'merchant_name'>, delayMinutes: number | null, now: string): string | null {
  const decision = item.decision
  if (!decision || decision.outcome !== 'APPROVED') return null
  if (delayMinutes === null) return `${decision.amount_label} reaches ${item.merchant_name} with the next settlement.`
  const at = hhmmAfter(decision.decided_at, delayMinutes)
  const left = minutesBetween(now, decision.decided_at)
  const credited = left !== null && left + delayMinutes <= 0
  return credited
    ? `${decision.amount_label} credited to ${item.merchant_name} at ${at}, with the settlement.`
    : `${decision.amount_label} reaches ${item.merchant_name} at ${at} on the replay clock, with the settlement.`
}

function Resolution({ item, delayMinutes, now }: { item: Case; delayMinutes: number | null; now: string }) {
  const note = item.status === 'APPROVED' ? creditNote(item, delayMinutes, now) : null
  return (
    <output className="resolution" data-status={item.status}>
      <span className="resolution__line">
        <span className={`badge badge--${CASE_STATUS_TONES[item.status]}`}>{item.status}</span>
        <span>
          {resolutionText(item)} · {hhmm(item.resolved_at)}
        </span>
      </span>
      {note ? (
        <span className="resolution__next">
          {note} <Link to={`/merchant/${item.merchant_id}`}>Open the phone</Link>
        </span>
      ) : null}
    </output>
  )
}

type ActionsProps = { item: Case; officerReady: boolean; onDecide: OfficerAction; delayMinutes: number | null; now: string }

function Actions({ item, officerReady, onDecide, delayMinutes, now }: ActionsProps) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'approve' | 'decline' | null>(null)
  const run = async (approve: boolean) => {
    setBusy(approve ? 'approve' : 'decline')
    try {
      await onDecide(approve, note)
    } finally {
      setBusy(null)
    }
  }
  if (item.status !== 'OPEN') return <Resolution item={item} delayMinutes={delayMinutes} now={now} />
  return (
    <div className="actions">
      <input className="input actions__note" placeholder="Note for the audit log (optional)" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} aria-label="Officer note" />
      <button type="button" className="btn btn--approve btn--lg" disabled={!officerReady || busy !== null} onClick={() => void run(true)}>
        {busy === 'approve' ? 'Approving…' : 'Approve'}
      </button>
      <button type="button" className="btn btn--decline btn--lg" disabled={!officerReady || busy !== null} onClick={() => void run(false)}>
        {busy === 'decline' ? 'Declining…' : 'Decline'}
      </button>
    </div>
  )
}

/** The headline sentence (plain words) with the rule under it; the server's summary is its tooltip. */
function CaseSummary({ item, referral }: { item: Case; referral: Decision | null }) {
  const headline = caseHeadline(item, referral)
  return (
    <div className="case-detail__summary">
      <p title={headline.text === item.summary_en ? undefined : item.summary_en}>{headline.text}</p>
      {headline.rule ? <p className="case-detail__rule">{headline.rule}</p> : null}
    </div>
  )
}

type Props = {
  item: Case
  now: string
  officerReady: boolean
  actionError: ApiError | null
  onDecide: OfficerAction
  onDismissError: () => void
  /** Simulated minutes from an officer approval to the credit (null when the policy is unknown). */
  delayMinutes?: number | null
  /** The policy engine's REFERRED decision that an officer decision supersedes (GET /api/decisions/{id}). */
  referral?: Decision | null
}

function decisionTitle(decision: Decision): string {
  return isOfficer(decision.decided_by) ? 'Officer decision' : 'Policy engine decision'
}

export function CaseDetail({ item, now, officerReady, actionError, onDecide, onDismissError, delayMinutes = null, referral = null }: Props) {
  const sla = slaState(item.due_by, now)
  const reason = referralDecision(item.decision, referral)
  const earlier = reason && reason.id !== item.decision?.id ? reason : null
  return (
    <article className="case-detail" aria-label={`Case ${item.id}`}>
      <header className="case-detail__head">
        <div>
          <p className="eyebrow">{CASE_KIND_LABELS[item.kind]}</p>
          <h2>
            {item.id} · <Link to={`/merchant/${item.merchant_id}`}>{item.merchant_name}</Link>
          </h2>
          <p className="muted num">
            Opened {dayLabel(item.opened_at)} {hhmm(item.opened_at)} · due {dayLabel(item.due_by)} {hhmm(item.due_by)}
            {item.status === 'OPEN' ? <span className={`sla sla--${sla.tone}`}> · SLA {sla.label}</span> : null}
          </p>
        </div>
        <span className={`badge badge--${CASE_STATUS_TONES[item.status]}`}>{item.status}</span>
      </header>
      <CaseSummary item={item} referral={referral} />
      {earlier ? <DecisionBlock decision={earlier} title={decisionTitle(earlier)} /> : null}
      {item.decision ? <DecisionBlock decision={item.decision} title={decisionTitle(item.decision)} /> : null}
      {reason ? <WhyHuman decision={reason} evidence={item.evidence} /> : null}
      {actionError ? <InlineError error={actionError} onDismiss={onDismissError} /> : null}
      <Actions item={item} officerReady={officerReady} onDecide={onDecide} delayMinutes={delayMinutes} now={now} />
      {!officerReady && item.status === 'OPEN' ? <p className="muted">Officer token unavailable: approvals need the demo session (GET /api/session).</p> : null}
      <Evidence evidence={item.evidence} />
      {item.decision && item.decision.checks.length > 0 ? (
        <section aria-label="Checks">
          <h3>Checks · rules {item.decision.rules_version}</h3>
          <Checks checks={item.decision.checks} />
        </section>
      ) : null}
    </article>
  )
}

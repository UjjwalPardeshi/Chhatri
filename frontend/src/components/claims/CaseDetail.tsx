/**
 * Case detail (SPEC §9.4, §12, §20 "Claims"): summary, decision with formula, evidence, checks
 * and one-tap Approve / Decline with the officer token; the new decision shows inline.
 */
import { useState } from 'react'
import { Link } from 'react-router'

import type { ApiError } from '../../api/client'
import type { Case, Decision } from '../../api/types'
import { dayLabel, hhmm, slaState } from '../../lib/time'
import { InlineError } from '../common/Status'
import { Checks } from './Checks'
import { Evidence } from './Evidence'
import { CASE_KIND_LABELS, CASE_STATUS_TONES, OUTCOME_TONES } from './labels'

export type OfficerAction = (approve: boolean, note: string) => Promise<void>

function DecisionBlock({ decision, title }: { decision: Decision; title: string }) {
  return (
    <div className="decision" data-outcome={decision.outcome}>
      <div className="decision__head">
        <span className="eyebrow">{title}</span>
        <span className={`badge badge--${OUTCOME_TONES[decision.outcome] ?? 'grey'}`}>{decision.outcome}</span>
        <strong className="decision__amount num">{decision.amount_label}</strong>
        <span className="muted num">
          {decision.id} · {decision.decided_by} · {hhmm(decision.decided_at)}
          {decision.supersedes ? ` · supersedes ${decision.supersedes}` : ''}
        </span>
      </div>
      {decision.referral_reason ? <p className="decision__reason">Why a human: {decision.referral_reason}</p> : null}
      {decision.explanation ? <p className="decision__formula num">{decision.explanation.formula_en}</p> : null}
    </div>
  )
}

function Actions({ item, officerReady, onDecide }: { item: Case; officerReady: boolean; onDecide: OfficerAction }) {
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
  if (item.status !== 'OPEN') {
    return (
      <output className="resolution">
        <span className={`badge badge--${CASE_STATUS_TONES[item.status]}`}>{item.status}</span>
        <span>
          {item.resolution} · {item.resolved_by} · {hhmm(item.resolved_at)}
        </span>
      </output>
    )
  }
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

type Props = { item: Case; now: string; officerReady: boolean; actionError: ApiError | null; onDecide: OfficerAction; onDismissError: () => void }

export function CaseDetail({ item, now, officerReady, actionError, onDecide, onDismissError }: Props) {
  const sla = slaState(item.due_by, now)
  return (
    <article className="case-detail" aria-label={`Case ${item.id}`}>
      <header className="case-detail__head">
        <div>
          <p className="eyebrow">{CASE_KIND_LABELS[item.kind]}</p>
          <h2>
            {item.id} · <Link to={`/merchant/${item.merchant_id}`}>{item.merchant_name}</Link>
          </h2>
          <p className="muted num">
            Opened {dayLabel(item.opened_at)} {hhmm(item.opened_at)} · due {hhmm(item.due_by)} {dayLabel(item.due_by)}
            {item.status === 'OPEN' ? <span className={`sla sla--${sla.tone}`}> · SLA {sla.label}</span> : null}
          </p>
        </div>
        <span className={`badge badge--${CASE_STATUS_TONES[item.status]}`}>{item.status}</span>
      </header>
      <p className="case-detail__summary">{item.summary_en}</p>
      {item.decision ? <DecisionBlock decision={item.decision} title={item.decision.decided_by.startsWith('officer:') ? 'Officer decision' : 'Policy engine decision'} /> : null}
      {actionError ? <InlineError error={actionError} onDismiss={onDismissError} /> : null}
      <Actions item={item} officerReady={officerReady} onDecide={onDecide} />
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

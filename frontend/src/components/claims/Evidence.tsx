/**
 * Case evidence (SPEC §12): expected vs actual by hour, slip image (opens large) + extraction +
 * KYC name + match score, silent days, the merchant's words, precedents ("No similar past cases
 * yet"). With the doctor rule (SPEC §9.2, chhatri-61 R10) the slip rows add the treating doctor and
 * the registration number, and a block says how the doctor's confirmation went and whether a real
 * doctor answered (`via`), when the server sends those keys.
 */
import { useState } from 'react'

import type { CaseEvidence, DoctorVerificationEvidence } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'
import { Icon } from '../common/Icon'
import { ModeChip } from '../common/ModeChip'
import { HourlyChart } from './HourlyChart'
import { NAME_SCORE_MIN } from './labels'
import { SlipLightbox } from './SlipLightbox'

export { HourlyChart } from './HourlyChart'

function SlipBlock({ evidence }: { evidence: CaseEvidence }) {
  const [open, setOpen] = useState(false)
  const slip = evidence.slip
  if (!slip) return null
  const score = evidence.name_score
  const rows: [string, string][] = [
    ['Patient name', slip.patient_name ?? 'not readable'],
    ['Admitted', slip.admission_date ? dayLabel(slip.admission_date) : 'not readable'],
    ['Discharged', slip.discharge_date ? dayLabel(slip.discharge_date) : '—'],
    ['Hospital', slip.hospital_name ?? '—'],
    ...(slip.doctor_name !== undefined || slip.doctor_registration_no !== undefined
      ? ([
          ['Doctor', slip.doctor_name ?? 'not readable'],
          ['Registration no.', slip.doctor_registration_no ?? 'not readable'],
        ] as [string, string][])
      : []),
    ['Document', slip.document_type ?? 'unknown'],
    ['Read confidence', `${Math.round(slip.confidence * 100)}% (${slip.source})`],
  ]
  const label = slip.mode ? (
    <tr key="reader">
      <th scope="row">Slip reader</th>
      <td>
        <ModeChip label={slip} />
      </td>
    </tr>
  ) : null
  return (
    <div className="slip-evidence">
      <button type="button" className="slip-evidence__img" aria-label="Open the slip large" onClick={() => setOpen(true)}>
        <img src={slip.media_url} alt="Hospital slip sent by the merchant" />
        <span className="slip-evidence__zoom" aria-hidden="true">
          <Icon name="zoom" size={14} /> Compare names
        </span>
      </button>
      {open ? <SlipLightbox evidence={evidence} onClose={() => setOpen(false)} /> : null}
      <div>
        <table className="table table--compact">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td>{v}</td>
              </tr>
            ))}
            {label}
            <tr>
              <th scope="row">KYC name</th>
              <td>{evidence.kyc_name ?? '—'}</td>
            </tr>
          </tbody>
        </table>
        {score !== undefined ? (
          <div className={`score ${score >= NAME_SCORE_MIN ? 'score--ok' : 'score--bad'}`}>
            <span>Name match</span>
            <span className="score__bar">
              <span style={{ width: `${Math.min(100, score)}%` }} />
              <i style={{ left: `${NAME_SCORE_MIN}%` }} title={`Needs ${NAME_SCORE_MIN}`} />
            </span>
            <strong className="num">
              {score} / 100 <span className="muted">(needs {NAME_SCORE_MIN})</span>
            </strong>
          </div>
        ) : null}
      </div>
    </div>
  )
}

const VERIFICATION_WORDS: Readonly<Record<DoctorVerificationEvidence['status'], string>> = {
  PENDING: 'Asked, waiting for the answer',
  CONFIRMED: 'Confirmed the visit',
  DENIED: 'Said the patient did not attend',
  NO_ANSWER: 'No answer',
}

const VIA_WORDS: Readonly<Record<string, string>> = {
  TELEGRAM: 'Telegram (a real doctor chat)',
  SIMULATED: 'simulated doctor (attendance register)',
  FALLBACK: 'simulated doctor (Telegram could not send)',
  FORCED: 'forced for the demo: nobody answered',
}

/** How the treating doctor's confirmation went (R10), and whether a real doctor answered. */
function DoctorVerification({ verification }: { verification: DoctorVerificationEvidence }) {
  const who = [verification.doctor_name, verification.hospital_name].filter(Boolean).join(' · ')
  const when = [verification.requested_at ? `asked ${hhmm(verification.requested_at)}` : null, verification.answered_at ? `answered ${hhmm(verification.answered_at)}` : null].filter(Boolean).join(' · ')
  return (
    <div className="doctor-verification" data-testid="doctor-verification" data-status={verification.status}>
      <h4>Treating doctor</h4>
      <p>
        <strong>{VERIFICATION_WORDS[verification.status] ?? verification.status}</strong>
        {who ? ` · ${who}` : null}
      </p>
      {when || verification.via ? (
        <p className="muted num">
          {when}
          {when && verification.via ? ' · ' : null}
          {verification.via ? `via ${VIA_WORDS[verification.via] ?? verification.via}` : null}
        </p>
      ) : null}
    </div>
  )
}

export function Evidence({ evidence, floorPct }: { evidence: CaseEvidence; floorPct?: number }) {
  const precedents = evidence.precedents ?? []
  return (
    <section className="evidence" aria-label="Evidence">
      <h3>Evidence</h3>
      {evidence.merchant_text ? (
        <blockquote className="merchant-quote hi" lang="hi">
          “{evidence.merchant_text}”
        </blockquote>
      ) : null}
      <SlipBlock evidence={evidence} />
      {evidence.doctor_verification ? <DoctorVerification verification={evidence.doctor_verification} /> : null}
      {evidence.silent_days && evidence.silent_days.length > 0 ? (
        <p className="silent-days">
          Silent days (no payments during business hours):{' '}
          {evidence.silent_days.map((d) => (
            <span key={d} className="badge badge--grey">
              {dayLabel(d)}
            </span>
          ))}
        </p>
      ) : null}
      {evidence.expected_vs_actual && evidence.expected_vs_actual.length > 0 ? <HourlyChart rows={evidence.expected_vs_actual} floorPct={floorPct} /> : null}
      <div className="precedents">
        <h4>Similar past cases</h4>
        {precedents.length === 0 ? (
          <p className="muted">No similar past cases yet</p>
        ) : (
          <ul>
            {precedents.map((p) => (
              <li key={`${p.subject_id}-${p.at}`}>
                <strong>{p.subject_id}</strong> · {p.kind} · {dayLabel(p.at)}: {p.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

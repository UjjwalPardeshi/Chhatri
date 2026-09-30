/**
 * Case evidence (SPEC §12): expected vs actual by hour, slip image + extraction + KYC name +
 * match score, silent days, the merchant's words, precedents ("No similar past cases yet").
 */
import type { CaseEvidence } from '../../api/types'
import { formatInr } from '../../lib/money'
import { dayLabel, hhmm } from '../../lib/time'
import { NAME_SCORE_MIN } from './labels'

const CHART_HEIGHT = 110

export function HourlyChart({ rows }: { rows: NonNullable<CaseEvidence['expected_vs_actual']> }) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.expected_paise, r.actual_paise)))
  const expected = rows.reduce((sum, r) => sum + r.expected_paise, 0)
  const actual = rows.reduce((sum, r) => sum + r.actual_paise, 0)
  return (
    <figure className="ev-chart">
      <figcaption>
        <span>Expected vs actual sales by hour · {dayLabel(rows[0]?.hour)}</span>
        <span className="num">
          <span className="swatch swatch--expected" /> expected {formatInr(expected)} <span className="swatch swatch--actual" /> actual {formatInr(actual)}
        </span>
      </figcaption>
      <div className="ev-chart__bars" style={{ height: CHART_HEIGHT }}>
        {rows.map((r) => (
          <div key={r.hour} className="ev-chart__hour" title={`${hhmm(r.hour)} · expected ${formatInr(r.expected_paise)} · actual ${formatInr(r.actual_paise)}`}>
            <span className="ev-chart__plot">
              <span className="ev-chart__expected" style={{ height: `${(r.expected_paise / max) * 100}%` }} />
              <span className="ev-chart__actual" style={{ height: `${(r.actual_paise / max) * 100}%` }} />
            </span>
            <span className="ev-chart__label num">{hhmm(r.hour).slice(0, 2)}</span>
          </div>
        ))}
      </div>
    </figure>
  )
}

function SlipBlock({ evidence }: { evidence: CaseEvidence }) {
  const slip = evidence.slip
  if (!slip) return null
  const score = evidence.name_score
  const rows: [string, string][] = [
    ['Patient name', slip.patient_name ?? 'not readable'],
    ['Admitted', slip.admission_date ? dayLabel(slip.admission_date) : 'not readable'],
    ['Discharged', slip.discharge_date ? dayLabel(slip.discharge_date) : '—'],
    ['Hospital', slip.hospital_name ?? '—'],
    ['Document', slip.document_type ?? 'unknown'],
    ['Read confidence', `${Math.round(slip.confidence * 100)}% (${slip.source})`],
  ]
  return (
    <div className="slip-evidence">
      <a className="slip-evidence__img" href={slip.media_url} target="_blank" rel="noreferrer">
        <img src={slip.media_url} alt="Hospital slip sent by the merchant" />
      </a>
      <div>
        <table className="table table--compact">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td>{v}</td>
              </tr>
            ))}
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

export function Evidence({ evidence }: { evidence: CaseEvidence }) {
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
      {evidence.expected_vs_actual && evidence.expected_vs_actual.length > 0 ? <HourlyChart rows={evidence.expected_vs_actual} /> : null}
      <div className="precedents">
        <h4>Similar past cases</h4>
        {precedents.length === 0 ? (
          <p className="muted">No similar past cases yet</p>
        ) : (
          <ul>
            {precedents.map((p) => (
              <li key={`${p.subject_id}-${p.at}`}>
                <strong>{p.subject_id}</strong> · {p.kind} · {dayLabel(p.at)} — {p.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

/**
 * The name check side by side inside "Why a human" (SPEC §9.2 NAME_MATCHES_KYC, §12 evidence
 * "slip image + extraction + KYC name + score"): a zoom of the slip's patient-name line, the name
 * read from the slip against the KYC name in large type, the match score on a 0-100 bar with the
 * pass mark, and "Compare names", which opens the whole slip beside both names.
 */
import { useState, type CSSProperties } from 'react'

import type { CaseEvidence } from '../../api/types'
import { Icon } from '../common/Icon'
import { NAME_SCORE_MIN } from './labels'
import { SlipLightbox } from './SlipLightbox'

/**
 * The patient name on the demo slips (backend/data/slips, copied to public/slips: 900 × 620 px,
 * name value at x 308, baseline near y 238).
 */
export const SLIP_NAME_CROP = Object.freeze({ x: 296, y: 202, w: 300, h: 52, imageW: 900 })
const PCT = 100
const MAX_SCORE = 100

/** Image size and offset that show only the crop box (margins in % of the box width). */
export function cropStyle(crop: typeof SLIP_NAME_CROP): CSSProperties {
  return { width: `${(crop.imageW / crop.w) * PCT}%`, marginLeft: `${(-crop.x / crop.w) * PCT}%`, marginTop: `${(-crop.y / crop.w) * PCT}%` }
}

function ScoreBar({ score }: { score: number }) {
  const ok = score >= NAME_SCORE_MIN
  return (
    <div className="name-compare__score" data-ok={ok}>
      <span className="name-compare__bar" aria-hidden="true">
        <span style={{ width: `${Math.min(MAX_SCORE, score)}%` }} />
        <i style={{ left: `${NAME_SCORE_MIN}%` }} />
      </span>
      <span className="num">
        <strong>{score}</strong>/{MAX_SCORE} <span className="muted">· needs {NAME_SCORE_MIN}</span>
      </span>
    </div>
  )
}

export function NameCompare({ evidence }: { evidence: CaseEvidence }) {
  const [open, setOpen] = useState(false)
  const slip = evidence.slip
  if (!slip?.patient_name || !evidence.kyc_name) return null
  const crop = SLIP_NAME_CROP
  return (
    <div className="name-compare">
      {slip.media_url ? (
        <button type="button" className="name-compare__crop" style={{ aspectRatio: `${crop.w} / ${crop.h}` }} aria-label="Zoom into the name on the slip" onClick={() => setOpen(true)}>
          <img src={slip.media_url} alt="" style={cropStyle(crop)} />
        </button>
      ) : null}
      <dl className="name-compare__names">
        <div>
          <dt>On the slip</dt>
          <dd>{slip.patient_name}</dd>
        </div>
        <div>
          <dt>KYC</dt>
          <dd>{evidence.kyc_name}</dd>
        </div>
      </dl>
      {evidence.name_score !== undefined ? <ScoreBar score={evidence.name_score} /> : null}
      {slip.media_url ? (
        <button type="button" className="btn name-compare__open" onClick={() => setOpen(true)}>
          <Icon name="zoom" size={14} /> Compare names
        </button>
      ) : null}
      {open ? <SlipLightbox evidence={evidence} onClose={() => setOpen(false)} /> : null}
    </div>
  )
}

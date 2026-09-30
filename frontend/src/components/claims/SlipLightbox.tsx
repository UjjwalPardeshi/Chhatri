/**
 * The hospital slip, large (SPEC §12 evidence, §20 "slip image + extraction + KYC name +
 * score"): the photo the merchant sent beside the name read from it and the KYC name, so the
 * officer can compare them on a projector. Escape, the close button or the backdrop closes it,
 * and focus goes back to whatever opened it. Rendered into <body> so no scroller moves under it.
 */
import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

import type { CaseEvidence } from '../../api/types'
import { useLatest } from '../../state/useLatest'
import { Icon } from '../common/Icon'
import { NAME_SCORE_MIN } from './labels'

type Props = { evidence: CaseEvidence; onClose: () => void }

export function SlipLightbox({ evidence, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const slip = evidence.slip
  const close = useLatest(onClose)
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeRef.current?.focus({ preventScroll: true })
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      opener?.focus({ preventScroll: true })
    }
  }, [close])
  if (!slip) return null
  const match = evidence.name_score === undefined ? null : evidence.name_score >= NAME_SCORE_MIN
  return createPortal(
    <dialog className="lightbox" open aria-modal="true" aria-label="Hospital slip">
      <button type="button" className="lightbox__backdrop" aria-label="Close" tabIndex={-1} onClick={onClose} />
      <div className="lightbox__panel">
        <img className="lightbox__img" src={slip.media_url} alt="Hospital slip sent by the merchant" />
        <aside className="lightbox__side">
          <p className="eyebrow">Name check</p>
          <dl className="lightbox__names">
            <div data-match={match === false ? 'no' : 'yes'}>
              <dt>On the slip</dt>
              <dd>{slip.patient_name ?? 'not readable'}</dd>
            </div>
            <div>
              <dt>KYC name</dt>
              <dd>{evidence.kyc_name ?? '—'}</dd>
            </div>
          </dl>
          {evidence.name_score !== undefined ? (
            <p className={`lightbox__score num ${match ? 'is-ok' : 'is-bad'}`}>
              Match score {evidence.name_score} / 100 <span className="muted">(needs {NAME_SCORE_MIN})</span>
            </p>
          ) : null}
          <p className="muted">
            {slip.hospital_name ?? 'Hospital not readable'} · read {Math.round(slip.confidence * 100)}% ({slip.source})
          </p>
        </aside>
        <button ref={closeRef} type="button" className="lightbox__close btn btn--icon" aria-label="Close the slip" onClick={onClose}>
          <Icon name="close" size={16} />
        </button>
      </div>
    </dialog>,
    document.body,
  )
}

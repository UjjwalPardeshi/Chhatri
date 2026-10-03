/**
 * The treating doctor's Telegram link, for the officer, under the chat-app switch on /merchant/:id (design 2.9, D8;
 * flag telegram_channel). One row per directory doctor: the name, the hospital and registration number, who answers
 * the doctor question now, and three buttons: Copy link (the clipboard, else the link shown selected to copy by hand),
 * Open in Telegram (a new tab: Telegram Desktop or Web logged in as the doctor) and New link (the old link stops
 * working and the doctor's chat is unenrolled). No QR code. The link is a secret: it is shown only on request and is
 * never logged. The merchant never sees this card's contents, and the doctor never sees an amount.
 */
import { useState } from 'react'

import type { DoctorEnrolment } from '../../api/types'
import type { DoctorLinksState } from '../../state/useDoctorLinks'
import { InlineError } from '../common/Status'

/** Who answers the doctor question for this doctor right now. */
export function doctorStatus(item: DoctorEnrolment): string {
  if (item.answers === 'FORCED') return 'Forced for the demo · no doctor answers, the claim goes to a person'
  if (item.enrolled && item.answers === 'TELEGRAM') return 'Enrolled · questions go to this Telegram chat'
  if (item.enrolled) return 'Telegram not live · the simulated doctor answers'
  return 'Not enrolled · the simulated doctor answers'
}

type CopyState = 'idle' | 'copied' | 'manual'

function CopyLink({ item }: { item: DoctorEnrolment & { deep_link: string } }) {
  const [copy, setCopy] = useState<CopyState>('idle')
  const copyLink = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('no clipboard')
      await navigator.clipboard.writeText(item.deep_link)
      setCopy('copied')
    } catch {
      setCopy('manual')
    }
  }
  return (
    <>
      <button type="button" className="btn" onClick={() => void copyLink()}>
        Copy link
      </button>
      {copy === 'copied' ? <output className="doctor-link__note">Link copied</output> : null}
      {copy === 'manual' ? (
        <input
          className="input doctor-link__field"
          readOnly
          value={item.deep_link}
          aria-label={`Enrolment link for ${item.doctor_name}`}
          ref={(el) => el?.select()}
          onFocus={(event) => event.currentTarget.select()}
        />
      ) : null}
    </>
  )
}

function DoctorRow({ item, state }: { item: DoctorEnrolment; state: DoctorLinksState }) {
  const link = item.deep_link
  return (
    <li className="doctor-link" data-enrolled={item.enrolled} data-answers={item.answers}>
      <div className="doctor-link__who">
        <strong>{item.doctor_name}</strong>
        <span className="muted">
          {item.hospital_name} · {item.registration_no}
        </span>
      </div>
      <p className="doctor-link__status" data-testid={`doctor-status-${item.registration_no}`}>
        {doctorStatus(item)}
      </p>
      <div className="doctor-link__actions">
        {link ? (
          <>
            <CopyLink item={{ ...item, deep_link: link }} />
            <a className="btn" href={link} target="_blank" rel="noreferrer">
              Open in Telegram
            </a>
          </>
        ) : (
          <p className="muted">No link yet: the bot's name is not known (Telegram not connected).</p>
        )}
        <button type="button" className="btn" disabled={state.busy !== null} onClick={() => void state.reset(item.registration_no)}>
          {state.busy === item.registration_no ? 'Making a new link…' : 'New link'}
        </button>
      </div>
    </li>
  )
}

export function DoctorLinkCard({ state }: { state: DoctorLinksState }) {
  if (!state.on) return null
  return (
    <section className="card merchant-card doctor-card" aria-label="Treating doctor">
      <h2>Treating doctor</h2>
      <p className="doctor-card__note">Officer only. Open the link on the doctor's own Telegram account: the doctor then gets “Did this patient attend?” with Yes and No.</p>
      {state.items === null && !state.error ? <p className="muted">Loading the doctor links…</p> : null}
      {state.items ? (
        <ul className="doctor-card__list">
          {state.items.map((item) => (
            <DoctorRow key={item.registration_no} item={item} state={state} />
          ))}
        </ul>
      ) : null}
      {state.error ? <InlineError error={state.error} /> : null}
    </section>
  )
}

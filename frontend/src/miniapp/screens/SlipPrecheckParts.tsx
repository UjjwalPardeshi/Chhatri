/**
 * The parts of the slip sheet (screens-and-flows 6.2 and 6.3, design 2.4): the six fields as plain text, the three
 * checklist lines, the notes, the buttons, the doctor question and the footer with the H26 label. No part shows a
 * confidence number, a percentage or a match with the KYC name, and no field can be edited: the way out of a wrong read
 * is another photo.
 */
import { Check, TriangleAlert } from 'lucide-react'

import type { DoctorConsent, SlipChecklistId, SlipChecklistLine, SlipPrecheck, SlipSlot, SlipSlotKey } from '../../api/types'
import { ModeBadge } from '../components/ModeBadge'
import type { CopyKey } from '../lib/copy'
import { t } from '../lib/copy'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import { retakesRemain } from './SlipPrecheckFlow'

const FIELD_LABEL: Readonly<Record<SlipSlotKey, CopyKey>> = {
  patient_name: 'SLIP_FIELD_NAME',
  admission_date: 'SLIP_FIELD_ADMITTED',
  discharge_date: 'SLIP_FIELD_DISCHARGED',
  hospital_name: 'SLIP_FIELD_HOSPITAL',
  doctor_name: 'SLIP_FIELD_DOCTOR',
  doctor_registration_no: 'SLIP_FIELD_DOCTOR_REG',
}

const CHECK_LABEL: Readonly<Record<SlipChecklistId, { PASS: CopyKey; WARN: CopyKey }>> = {
  photo_readable: { PASS: 'SLIP_CHECK_READABLE_PASS', WARN: 'SLIP_CHECK_READABLE_WARN' },
  name_on_slip: { PASS: 'SLIP_CHECK_NAME_PASS', WARN: 'SLIP_CHECK_NAME_WARN' },
  dates_on_slip: { PASS: 'SLIP_CHECK_DATES_PASS', WARN: 'SLIP_CHECK_DATES_WARN' },
}

const DATE_SLOTS: readonly SlipSlotKey[] = ['admission_date', 'discharge_date']

function valueOf(slot: SlipSlot, lang: Lang): string {
  if (slot.state === 'READ' && slot.value !== null) return DATE_SLOTS.includes(slot.key) ? formatDate(slot.value, lang) : slot.value
  return t(slot.state === 'MISSING' ? 'slip.not_clear' : 'SLIP_FIELD_NOT_ON_SLIP', lang)
}

export function SlipFields({ slots, lang, muted }: { slots: readonly SlipSlot[]; lang: Lang; muted: boolean }) {
  return (
    <dl data-testid="slip-fields" className={muted ? 'flex flex-col text-ink-3' : 'flex flex-col'}>
      {slots.map((slot) => (
        <div key={slot.key} data-testid={`slip-field-${slot.key}`} data-state={slot.state} className="flex items-baseline justify-between gap-3 border-b py-2 text-sm last:border-b-0">
          <dt className="text-ink-2">{t(FIELD_LABEL[slot.key], lang)}</dt>
          <dd className="text-right font-medium">{valueOf(slot, lang)}</dd>
        </div>
      ))}
    </dl>
  )
}

export function SlipChecklist({ lines, lang }: { lines: readonly SlipChecklistLine[]; lang: Lang }) {
  return (
    <ul data-testid="slip-checklist" className="flex flex-col gap-2">
      {lines.map((line) => {
        const Icon = line.state === 'PASS' ? Check : TriangleAlert
        return (
          <li key={line.id} className="flex items-start gap-2 text-sm">
            <Icon className={line.state === 'PASS' ? 'mt-0.5 size-4 shrink-0 text-live-ink' : 'mt-0.5 size-4 shrink-0 text-referred-ink'} aria-hidden="true" />
            <span data-testid={`slip-check-${line.id}`} data-state={line.state}>
              {t(CHECK_LABEL[line.id][line.state], lang)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/** The notes of fs-02 9.2: no discharge date (normal while in hospital) and a name that is not in Latin letters. */
export function SlipNotes({ check, lang }: { check: SlipPrecheck; lang: Lang }) {
  const notes: CopyKey[] = []
  if (check.status === 'READY' && check.slots.some((slot) => slot.key === 'discharge_date' && slot.state === 'NOT_ON_SLIP')) notes.push('SLIP_NOTE_NO_DISCHARGE')
  if (check.slots.some((slot) => slot.note === 'SLIP_NOTE_NAME_NOT_LATIN')) notes.push('SLIP_NOTE_NAME_NOT_LATIN')
  if (notes.length === 0) return null
  return (
    <div data-testid="slip-notes" className="flex flex-col gap-1 text-sm text-ink-2">
      {notes.map((key) => (
        <p key={key}>{t(key, lang)}</p>
      ))}
    </div>
  )
}

type ActionsProps = { check: SlipPrecheck; lang: Lang; busy: boolean; online: boolean; onConfirm: () => void; onRetake: () => void; onTeam: () => void }

/** READY: confirm or another photo. RETAKE and NEEDS_TEAM: the team, and another photo while photos remain. */
export function SlipActions({ check, lang, busy, online, onConfirm, onRetake, onTeam }: ActionsProps) {
  const blocked = busy || !online
  return (
    <div className="flex flex-col gap-2">
      {check.status === 'READY' ? (
        <Button data-testid="slip-confirm" size="lg" disabled={blocked} onClick={onConfirm}>
          {t('SLIP_ACTION_CONFIRM', lang)}
        </Button>
      ) : null}
      {check.status === 'RETAKE' || check.status === 'NEEDS_TEAM' ? (
        <Button data-testid="slip-team" size="lg" disabled={blocked} onClick={onTeam}>
          {t('SLIP_ACTION_TEAM', lang)}
        </Button>
      ) : null}
      {retakesRemain(check) ? (
        <Button data-testid="slip-retake" size="lg" variant="outline" disabled={blocked} onClick={onRetake}>
          {t('SLIP_ACTION_RETAKE', lang)}
        </Button>
      ) : null}
    </div>
  )
}

type ConsentProps = { consent: DoctorConsent; lang: Lang; busy: boolean; online: boolean; onAnswer: (yes: boolean) => void }

/**
 * The doctor question (design 2.6) in the server's own words: Hindi for Hindi and Marathi (the question has no Marathi
 * yet), English for English. Yes or No: either way the claim is filed, and No sends it to a person.
 */
export function ConsentStep({ consent, lang, busy, online, onAnswer }: ConsentProps) {
  const english = lang === 'en'
  const blocked = busy || !online
  return (
    <section data-testid="slip-consent-card" aria-labelledby="slip-consent-title" className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <h3 id="slip-consent-title" className="text-sm font-medium text-ink-2">{t('slip.consent.title', lang)}</h3>
      <p data-testid="slip-consent-question" lang={english ? 'en' : 'hi'} className="text-md">
        {english ? consent.question_en : consent.question_hi}
      </p>
      <p className="text-xs text-ink-3">{t('slip.consent.note', lang)}</p>
      <div className="flex flex-col gap-2">
        <Button data-testid="slip-consent-yes" size="lg" disabled={blocked} onClick={() => onAnswer(true)}>
          {t('DOCTOR_CONSENT_YES', lang)}
        </Button>
        <Button data-testid="slip-consent-no" size="lg" variant="outline" disabled={blocked} onClick={() => onAnswer(false)}>
          {t('DOCTOR_CONSENT_NO', lang)}
        </Button>
      </div>
    </section>
  )
}

/** The H26 label: the mode word, the line for that mode, and the provider, model and reason behind "Details". */
export function SlipFooter({ check, lang }: { check: SlipPrecheck; lang: Lang }) {
  return (
    <footer data-testid="slip-footer" className="flex flex-col gap-2 border-t pt-3 text-xs text-ink-3">
      <div className="flex items-center gap-2">
        <ModeBadge mode={check.mode} testId="slip-mode" />
        {check.mode === 'SIMULATED' ? <span>{t('sim.slip', lang)}</span> : null}
        {check.mode === 'FALLBACK' ? <span>{t('mode.FALLBACK.hint', lang)}</span> : null}
      </div>
      <details data-testid="slip-details">
        <summary className="min-h-11 cursor-pointer py-3">{t('slip.details', lang)}</summary>
        <ul className="flex flex-col gap-1">
          <li>{t('slip.details.provider', lang, { provider: check.provider })}</li>
          {check.model ? <li>{t('slip.details.model', lang, { model: check.model })}</li> : null}
          {check.fallback_reason ? <li>{t('slip.details.reason', lang, { reason: check.fallback_reason })}</li> : null}
        </ul>
      </details>
    </footer>
  )
}

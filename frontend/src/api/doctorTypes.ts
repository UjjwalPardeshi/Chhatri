/**
 * The doctor confirmation on the wire (design 2.4, 2.6, 2.9): the doctor question of a pre-check and its answer, the
 * confirm and open answers of the slip pre-check, and the officer's doctor enrolment links. Split from types.ts, which
 * re-exports everything here.
 */
import type { Message, SlipPrecheck } from './types'

/** The purpose word of the doctor question on the wire: the chat card, its meta and the confirm answer (design 2.4). */
export const DOCTOR_CONSENT_PURPOSE = 'doctor_verification'
/** The consent-ledger purpose the answer is written under (backend `consent/notice.py` DOCTOR); never in the consent centre list. */
export const DOCTOR_LEDGER_PURPOSE = 'DOCTOR_CONFIRMATION'
export const DOCTOR_CONSENT_STATUSES = ['ASKED', 'GIVEN', 'REFUSED'] as const
export type DoctorConsentStatus = (typeof DOCTOR_CONSENT_STATUSES)[number]
/** The doctor question of a pre-check (design 2.4): the server's own Hindi and English words, and the answer once given. */
export type DoctorConsent = {
  purpose: typeof DOCTOR_CONSENT_PURPOSE
  status: DoctorConsentStatus
  precheck_id: string
  doctor_name: string | null
  hospital_name: string | null
  question_hi: string
  question_en: string
  answered_at: string | null
}
/** The doctor is being asked; the decision follows when they answer (design 2.4, chhatri-61 R3). */
export type DoctorCheck = { status: 'PENDING'; doctor_name: string | null; hospital_name: string | null }
export type DoctorCheckStep = 'STARTED' | 'ASKED' | 'CONFIRMED'
export type PrecheckConfirm = {
  precheck_id: string
  status: 'AWAITING_CONSENT' | 'CONFIRMED'
  confirmed_as: 'FIELDS_CONFIRMED' | 'SENT_TO_TEAM'
  claim_id: string | null
  decision_id: string | null
  outcome: 'APPROVED' | 'REFERRED' | 'DECLINED' | null
  case_id: string | null
  messages: Message[]
  consent: DoctorConsent | null
  doctor_check: DoctorCheck | null
}
/** GET /api/merchants/{id}/slip-precheck/open: the open check-in, and the pre-check or the doctor question it waits on. */
export type PrecheckOpen = {
  merchant_id: string
  checkin_open: boolean
  first_silent_day: string | null
  precheck: SlipPrecheck | null
  awaiting_consent: DoctorConsent | null
}
/** One directory doctor's Telegram enrolment link (officer only, design 2.9). The link is a secret: never logged. */
export type DoctorAnswers = 'TELEGRAM' | 'SIMULATED' | 'FORCED'
export type DoctorEnrolment = {
  registration_no: string
  doctor_name: string
  hospital_id: string
  hospital_name: string
  enrolled: boolean
  deep_link: string | null
  answers: DoctorAnswers
}

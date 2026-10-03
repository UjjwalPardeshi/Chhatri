/**
 * The treating doctor in the mock (SPEC §9.2, design 2.3 to 2.6): the one directory doctor of the demo (Dr S. Rao of KEM
 * Hospital, Parel), the doctor question the pre-check asks after the merchant confirms what was read, and the five
 * doctor checks. The mock has no Telegram: a simulated doctor answers from the stage attendance register (Anil R. Jadhav,
 * 20 August 2025), and is never asked about a slip a person must look at anyway (chhatri-61 R4). Nothing here names a
 * phone number or a chat: the doctor is reached through the directory only.
 */
import type { Check, DoctorConsent, Message, SlipEvidence } from '../api/types'
import { DOCTOR_CONSENT_PURPOSE, DOCTOR_LEDGER_PURPOSE } from '../api/types'
import { MSG, type Bilingual } from './catalogue'
import { check } from './claims'
import type { MockMerchant } from './fixtures'
import type { MockRuntime } from './runtime'

export type DirectoryDoctor = { registration_no: string; name: string; hospital_id: string; hospital_name: string; aliases: readonly string[] }

export const DIRECTORY_DOCTORS: readonly DirectoryDoctor[] = [
  { registration_no: 'MMC-2011-45817', name: 'Dr S. Rao', hospital_id: 'H-KEM', hospital_name: 'KEM Hospital, Parel', aliases: ['KEM Hospital, Parel', 'KEM Hospital', 'K.E.M. Hospital Parel'] },
]

/** The stage register of the simulated doctor: who attended which hospital on which day. */
const ATTENDANCE: readonly { hospital_id: string; patient_name: string; visit_date: string }[] = [{ hospital_id: 'H-KEM', patient_name: 'Anil R. Jadhav', visit_date: '2025-08-20' }]

type SlipFacts = Pick<SlipEvidence, 'patient_name' | 'admission_date' | 'hospital_name' | 'doctor_name' | 'doctor_registration_no'> & { name_score: number | null }

/** The merchant's answer to the doctor question; `precheckId` ties the consent record to its pre-check. */
export type DoctorStep = { consent: boolean; precheckId: string }

const norm = (value: string | null | undefined): string => (value ?? '').toLowerCase().replace(/[^a-z0-9]/g, '')

export function findDoctor(slip: Pick<SlipFacts, 'hospital_name' | 'doctor_registration_no'>): DirectoryDoctor | null {
  const hospital = norm(slip.hospital_name)
  return DIRECTORY_DOCTORS.find((d) => d.aliases.some((alias) => norm(alias) === hospital) && norm(d.registration_no) === norm(slip.doctor_registration_no)) ?? null
}

/** The question in the server's words (design 2.6), with the directory's names when the doctor resolves. */
export function consentQuestion(slip: SlipFacts): { doctor: DirectoryDoctor | null; text: Bilingual } {
  const doctor = findDoctor(slip)
  return { doctor, text: doctor ? MSG.doctorConsentAsk(doctor.name, doctor.hospital_name) : MSG.doctorConsentAskGeneric }
}

export function consentView(precheckId: string, slip: SlipFacts, status: DoctorConsent['status'], answeredAt: string | null): DoctorConsent {
  const { doctor, text } = consentQuestion(slip)
  return {
    purpose: DOCTOR_CONSENT_PURPOSE,
    status,
    precheck_id: precheckId,
    doctor_name: doctor?.name ?? slip.doctor_name ?? null,
    hospital_name: doctor?.hospital_name ?? slip.hospital_name ?? null,
    question_hi: text.hi ?? text.en,
    question_en: text.en,
    answered_at: answeredAt,
  }
}

/** Sends the question as a chat message with its two buttons (design 2.6 message shape 2). */
export function askConsent(rt: MockRuntime, merchantId: string, precheckId: string, slip: SlipFacts): Message {
  const view = consentView(precheckId, slip, 'ASKED', null)
  const card = {
    consent_for: precheckId,
    purpose: DOCTOR_CONSENT_PURPOSE,
    doctor_name: view.doctor_name,
    hospital_name: view.hospital_name,
    actions: [
      { kind: 'CONSENT_YES', label_hi: 'हाँ, पूछ लीजिए', label_en: 'Yes, ask them' },
      { kind: 'CONSENT_NO', label_hi: 'नहीं', label_en: 'No' },
    ],
  }
  return rt.send(merchantId, {
    kind: 'TEXT',
    text: { hi: view.question_hi, en: view.question_en },
    card: card as never,
    meta: { precheck_id: precheckId, consent_purpose: DOCTOR_CONSENT_PURPOSE },
  })
}

/**
 * Records the answer in the ledger's words (Yes ACTIVE, No WITHDRAWN, update 15:05), audited like backend
 * `ConsentBook.answer`: consent.granted or consent.refused, purpose DOCTOR_CONFIRMATION, never a patient, doctor or slip value.
 */
export function recordConsent(rt: MockRuntime, merchantId: string, step: DoctorStep): void {
  const action = step.consent ? 'consent.granted' : 'consent.refused'
  rt.record(`merchant:${merchantId}`, action, 'consent', `${DOCTOR_LEDGER_PURPOSE}:${step.precheckId}`, { merchant_id: merchantId, purpose: DOCTOR_LEDGER_PURPOSE, source: 'CLAIM_APP', precheck_id: step.precheckId })
}

function attended(doctor: DirectoryDoctor, slip: SlipFacts): boolean {
  return ATTENDANCE.some((row) => row.hospital_id === doctor.hospital_id && norm(row.patient_name) === norm(slip.patient_name) && row.visit_date === slip.admission_date)
}

/**
 * The five doctor checks, in the engine's order. The simulated doctor is asked only with the merchant's Yes, a known
 * doctor and a slip that nothing else sends to a person (its name matches); it says the progress line in the chat.
 */
export function doctorChecks(rt: MockRuntime, merchant: MockMerchant, slip: SlipFacts, step: DoctorStep): Check[] {
  const doctor = findDoctor(slip)
  const hospitalKnown = doctor !== null || slip.hospital_name !== null
  const nameOk = slip.name_score !== null && slip.name_score >= 85
  const asked = step.consent && doctor !== null && nameOk
  const confirmed = asked && attended(doctor, slip)
  if (asked) {
    rt.send(merchant.id, {
      kind: 'TEXT',
      text: MSG.doctorConfirmedVisit(doctor.name),
      meta: { doctor_check: 'CONFIRMED', doctor_name: doctor.name, hospital_name: doctor.hospital_name, mode: 'SIMULATED', provider: 'simulated' },
    })
  }
  const notAsked = step.consent ? 'not asked: a person checks this slip first' : 'not asked: no consent'
  return [
    check('HOSPITAL_IDENTIFIED', 'HARD', hospitalKnown ? 'PASS' : 'FAIL', 'Hospital found in the directory', slip.hospital_name ?? 'no hospital read', 'in the directory'),
    check('DOCTOR_IDENTIFIED', 'HARD', doctor ? 'PASS' : 'FAIL', "Doctor on that hospital's register", slip.doctor_registration_no ?? 'no registration no. read', "on the hospital's register"),
    check('VERIFICATION_CONSENT', 'SOFT', step.consent ? 'PASS' : 'FAIL', 'Merchant agreed to the confirmation', step.consent ? 'agreed' : 'declined', 'agreed'),
    check('DOCTOR_NOT_DENIED', 'HARD', asked && !confirmed ? 'FAIL' : 'PASS', 'Doctor did not deny the visit', asked ? (confirmed ? 'confirmed' : 'denied') : 'not asked', 'not denied'),
    check('DOCTOR_CONFIRMED', 'SOFT', confirmed ? 'PASS' : 'UNSURE', 'Doctor confirmed the visit', asked ? 'confirmed (simulated doctor)' : notAsked, 'confirmed'),
  ]
}

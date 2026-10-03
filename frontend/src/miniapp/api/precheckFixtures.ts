/**
 * Test fixtures: the READY, RETAKE and NEEDS_TEAM examples of data-model 5.3 (six slots, design 2.3) and the confirm and
 * open answers of design 2.4, as the API sends them.
 */
import type { DoctorConsent, PrecheckOpen, SlipPrecheck } from '../../api/types'

export const READY_PRECHECK: SlipPrecheck = {
  precheck_id: 'PC-000001',
  merchant_id: 'S-0142',
  status: 'READY',
  attempt: 1,
  retakes_left: 2,
  media_id: 'MD-000002',
  document: { type: 'admission_slip', accepted: true },
  slots: [
    { key: 'patient_name', value: 'Anil R. Jadhav', state: 'READ', note: null },
    { key: 'admission_date', value: '2025-08-20', state: 'READ', note: null },
    { key: 'discharge_date', value: null, state: 'NOT_ON_SLIP', note: null },
    { key: 'hospital_name', value: 'KEM Hospital, Parel', state: 'READ', note: null },
    { key: 'doctor_name', value: 'Dr S. Rao', state: 'READ', note: null },
    { key: 'doctor_registration_no', value: 'MMC-2011-45817', state: 'READ', note: null },
  ],
  checklist: [
    { id: 'photo_readable', state: 'PASS' },
    { id: 'name_on_slip', state: 'PASS' },
    { id: 'dates_on_slip', state: 'PASS' },
  ],
  gate: { passed: true, confidence: 0.94, minimum: 0.8 },
  reason: null,
  guidance: null,
  next_action: { kind: 'CONFIRM_FIELDS', label_hi: 'हाँ, सही है', label_en: 'Yes, this is right' },
  source: { kind: 'SLIP', label: 'Hospital slip read', ref: 'slip:MD-000002', as_of: '2025-08-21T11:25:00+05:30', origin: 'SIMULATED', clause: 'C3' },
  mode: 'SIMULATED',
  provider: 'simulated',
  model: null,
  fallback_reason: 'NO_KEY',
  attempts: [],
}

export const RETAKE_PRECHECK: SlipPrecheck = {
  ...READY_PRECHECK,
  status: 'RETAKE',
  document: { type: null, accepted: false },
  slots: [
    { key: 'patient_name', value: null, state: 'MISSING', note: null },
    { key: 'admission_date', value: null, state: 'MISSING', note: null },
    { key: 'discharge_date', value: null, state: 'NOT_ON_SLIP', note: null },
    { key: 'hospital_name', value: null, state: 'NOT_ON_SLIP', note: null },
    { key: 'doctor_name', value: null, state: 'NOT_ON_SLIP', note: null },
    { key: 'doctor_registration_no', value: null, state: 'NOT_ON_SLIP', note: null },
  ],
  checklist: [
    { id: 'photo_readable', state: 'WARN' },
    { id: 'name_on_slip', state: 'WARN' },
    { id: 'dates_on_slip', state: 'WARN' },
  ],
  gate: { passed: false, confidence: 0.22, minimum: 0.8 },
  reason: 'LOW_CONFIDENCE',
  guidance: {
    key: 'SLIP_RETAKE_CLEAR',
    text_hi: 'फ़ोटो साफ़ नहीं है। रोशनी में, पर्ची सीधी रखकर, पूरी पर्ची की फ़ोटो भेजिए।',
    text_en: 'The photo is not clear. Please take it in good light, with the slip flat and fully in view.',
  },
  next_action: { kind: 'RETAKE_PHOTO', label_hi: 'दूसरी फ़ोटो भेजें', label_en: 'Send another photo' },
}

export const NEEDS_TEAM_PRECHECK: SlipPrecheck = {
  ...RETAKE_PRECHECK,
  status: 'NEEDS_TEAM',
  gate: { passed: false, confidence: 0, minimum: 0.8 },
  reason: 'READ_FAILED',
  guidance: {
    key: 'SLIP_NO_READ',
    text_hi: 'अभी पर्ची पढ़ी नहीं जा सकी। आप इसे हमारी टीम को भेज सकते हैं, वे इसे देखेंगे।',
    text_en: 'We could not read the slip just now. You can send it to our team, who will look at it.',
  },
  next_action: { kind: 'SEND_TO_TEAM', label_hi: 'हमारी टीम को भेजें', label_en: 'Send to our team' },
  mode: 'FALLBACK',
  provider: 'none',
  fallback_reason: 'TIMEOUT',
  attempts: [
    { provider: 'gemini', outcome: 'TIMEOUT', ms: 3004 },
    { provider: 'sarvam', outcome: 'PROVIDER_ERROR', ms: 1210 },
  ],
}

export const CONFIRMED_RESPONSE = {
  precheck_id: 'PC-000001',
  status: 'CONFIRMED',
  confirmed_as: 'FIELDS_CONFIRMED',
  claim_id: 'CL-000001',
  decision_id: 'D-000001',
  outcome: 'APPROVED',
  case_id: null,
  messages: [],
  consent: null,
  doctor_check: null,
} as const

export const ASKED_CONSENT: DoctorConsent = {
  purpose: 'doctor_verification',
  status: 'ASKED',
  precheck_id: 'PC-000001',
  doctor_name: 'Dr S. Rao',
  hospital_name: 'KEM Hospital, Parel',
  question_hi: 'क्या हम KEM Hospital, Parel के Dr S. Rao से आपकी भर्ती की पुष्टि करवा सकते हैं? उन्हें सिर्फ़ आपका नाम और तारीख़ बताई जाएगी।',
  question_en: 'May we ask Dr S. Rao at KEM Hospital, Parel to confirm your visit? They will see only your name and the date.',
  answered_at: null,
}

/** CONFIRM with the doctor rule on: nothing is filed yet, the doctor question is asked. */
export const AWAITING_CONSENT_RESPONSE = {
  precheck_id: 'PC-000001',
  status: 'AWAITING_CONSENT',
  confirmed_as: 'FIELDS_CONFIRMED',
  claim_id: null,
  decision_id: null,
  outcome: null,
  case_id: null,
  messages: [],
  consent: ASKED_CONSENT,
  doctor_check: null,
} as const

/** CONSENT_YES: the claim is filed and waits for the doctor (interim REFERRED, no case yet). */
export const DOCTOR_PENDING_RESPONSE = {
  ...CONFIRMED_RESPONSE,
  outcome: 'REFERRED',
  consent: { ...ASKED_CONSENT, status: 'GIVEN', answered_at: '2025-08-21T11:21:00+05:30' },
  doctor_check: { status: 'PENDING', doctor_name: 'Dr S. Rao', hospital_name: 'KEM Hospital, Parel' },
} as const

export const OPEN_READY: PrecheckOpen = { merchant_id: 'S-0142', checkin_open: true, first_silent_day: '2025-08-20', precheck: READY_PRECHECK, awaiting_consent: null }

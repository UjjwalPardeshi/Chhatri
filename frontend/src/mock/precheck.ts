/**
 * Mock N3 slip pre-check logic (data-model 5.3, fs-02 section 7.3): reads a sample slip with the simulator the browser
 * has (provider `mock`, reason MOCK_BACKEND), applies the status table (first row that applies) and keeps the checks of
 * one scenario load in memory. Nothing here decides money: a confirmed or sent slip goes to the BUILT mock personal
 * claim, whose checks run exactly as they do for a slip sent in the chat. The doctor rule is on (as on stage), so a
 * read slip without the doctor or the registration number is a retake (DOCTOR_MISSING, design D7).
 */
import type { PrecheckGuidanceKey, PrecheckReason, SlipChecklistLine, SlipPrecheck, SlipSlot } from '../api/types'
import { MockHttpError } from './http'
import { SAMPLE_SLIPS, SLIP_CONFIDENCE_MIN } from './personal'
import type { MockRuntime } from './runtime'

export type SlipReading = (typeof SAMPLE_SLIPS)[string]
export const MAX_PHOTOS = 3

type Guidance = { text_hi: string; text_en: string }

/** Copy deck 12.2, quoted. */
export const GUIDANCE: Readonly<Record<PrecheckGuidanceKey, Guidance>> = {
  SLIP_RETAKE_DOCUMENT: {
    text_en: 'This does not look like a hospital document. Please send a photo of the admission slip, the discharge paper or the bill.',
    text_hi: 'यह अस्पताल की पर्ची नहीं लग रही। कृपया भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की फ़ोटो भेजिए।',
  },
  SLIP_RETAKE_CLEAR: {
    text_en: 'The photo is not clear. Please take it in good light, with the slip flat and fully in view.',
    text_hi: 'फ़ोटो साफ़ नहीं है। रोशनी में, पर्ची सीधी रखकर, पूरी पर्ची की फ़ोटो भेजिए।',
  },
  SLIP_RETAKE_NAME: {
    text_en: "The patient's name is not clear. Please send a photo where the whole name is in view.",
    text_hi: 'मरीज़ का नाम साफ़ नहीं दिख रहा। नाम वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।',
  },
  SLIP_RETAKE_DATE: {
    text_en: 'The admission date is not clear. Please send a photo where the whole date is in view.',
    text_hi: 'भर्ती की तारीख़ साफ़ नहीं दिख रही। तारीख़ वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।',
  },
  SLIP_RETAKE_DOCTOR: {
    text_en: "The doctor's name and registration number are not clear. Please send a photo where the doctor's name and number are fully in view.",
    text_hi: 'डॉक्टर का नाम और रजिस्ट्रेशन नंबर साफ़ नहीं दिख रहा। डॉक्टर के नाम वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।',
  },
  SLIP_NO_READ: {
    text_en: 'We could not read the slip just now. You can send it to our team, who will look at it.',
    text_hi: 'अभी पर्ची पढ़ी नहीं जा सकी। आप इसे हमारी टीम को भेज सकते हैं, वे इसे देखेंगे।',
  },
  SLIP_PHOTO_LIMIT: {
    text_en: 'You have already sent several photos. Please send this one to our team now.',
    text_hi: 'आप पहले भी फ़ोटो भेज चुके हैं। अब इसे हमारी टीम को भेज दीजिए।',
  },
}

const REASON_GUIDANCE: Readonly<Record<PrecheckReason, PrecheckGuidanceKey>> = {
  READ_FAILED: 'SLIP_NO_READ',
  INJECTION_SUSPECTED: 'SLIP_NO_READ',
  NOT_A_HOSPITAL_DOCUMENT: 'SLIP_RETAKE_DOCUMENT',
  LOW_CONFIDENCE: 'SLIP_RETAKE_CLEAR',
  NAME_MISSING: 'SLIP_RETAKE_NAME',
  DATES_NOT_CLEAR: 'SLIP_RETAKE_DATE',
  DOCTOR_MISSING: 'SLIP_RETAKE_DOCTOR',
}

const ACTIONS = {
  CONFIRM_FIELDS: { kind: 'CONFIRM_FIELDS', label_hi: 'हाँ, सही है', label_en: 'Yes, this is right' },
  RETAKE_PHOTO: { kind: 'RETAKE_PHOTO', label_hi: 'दूसरी फ़ोटो भेजें', label_en: 'Send another photo' },
  SEND_TO_TEAM: { kind: 'SEND_TO_TEAM', label_hi: 'हमारी टीम को भेजें', label_en: 'Send to our team' },
} as const

const MEDICAL_TYPES: readonly (string | null)[] = ['admission_slip', 'discharge_summary', 'prescription', 'bill']
const NON_LATIN_LETTER = /(?!\p{Script=Latin})\p{L}/u

/** The first row of the status table of data-model 5.3 that applies, or null when the slip is READY. */
export function retakeReason(read: SlipReading, replayDay: string): PrecheckReason | null {
  const accepted = MEDICAL_TYPES.includes(read.document_type)
  if (read.document_type === 'other') return 'NOT_A_HOSPITAL_DOCUMENT'
  if (!read.patient_name && !read.admission_date && read.document_type === null) return 'LOW_CONFIDENCE'
  if (!read.patient_name) return 'NAME_MISSING'
  const badAdmission = !read.admission_date || read.admission_date > replayDay
  const dischargeBefore = read.admission_date !== null && read.discharge_date !== null && read.discharge_date < read.admission_date
  if (badAdmission || dischargeBefore) return 'DATES_NOT_CLEAR'
  if (!read.doctor_name || !read.doctor_registration_no) return 'DOCTOR_MISSING'
  if (!accepted || read.confidence < SLIP_CONFIDENCE_MIN) return 'LOW_CONFIDENCE'
  return null
}

const slot = (key: SlipSlot['key'], value: string | null, empty: 'MISSING' | 'NOT_ON_SLIP', note: string | null = null): SlipSlot => ({
  key,
  value: value || null,
  state: value ? 'READ' : empty,
  note: value ? note : null,
})

const line = (id: SlipChecklistLine['id'], pass: boolean): SlipChecklistLine => ({ id, state: pass ? 'PASS' : 'WARN' })

function slots(read: SlipReading): SlipSlot[] {
  return [
    slot('patient_name', read.patient_name, 'MISSING', read.patient_name && NON_LATIN_LETTER.test(read.patient_name) ? 'SLIP_NOTE_NAME_NOT_LATIN' : null),
    slot('admission_date', read.admission_date, 'MISSING'),
    slot('discharge_date', read.discharge_date, 'NOT_ON_SLIP'),
    slot('hospital_name', read.hospital_name, 'NOT_ON_SLIP'),
    slot('doctor_name', read.doctor_name ?? null, 'NOT_ON_SLIP'),
    slot('doctor_registration_no', read.doctor_registration_no ?? null, 'NOT_ON_SLIP'),
  ]
}

function checklist(read: SlipReading): SlipChecklistLine[] {
  const readable = MEDICAL_TYPES.includes(read.document_type) && read.confidence >= SLIP_CONFIDENCE_MIN
  return [line('photo_readable', readable), line('name_on_slip', Boolean(read.patient_name)), line('dates_on_slip', Boolean(read.admission_date))]
}

export type PrecheckInputs = { rt: MockRuntime; merchantId: string; id: string; mediaId: string; attempt: number; read: SlipReading }

/** The H26 label of the browser's reader: SIMULATED, provider `mock`, reason MOCK_BACKEND. */
export function buildPrecheck({ rt, merchantId, id, mediaId, attempt, read }: PrecheckInputs): SlipPrecheck {
  const reason = retakeReason(read, rt.scenario.day)
  const lastPhoto = attempt >= MAX_PHOTOS
  const status = reason === null ? 'READY' : lastPhoto ? 'NEEDS_TEAM' : 'RETAKE'
  const guidanceKey = reason === null ? null : lastPhoto ? 'SLIP_PHOTO_LIMIT' : REASON_GUIDANCE[reason]
  const accepted = MEDICAL_TYPES.includes(read.document_type)
  return {
    precheck_id: id,
    merchant_id: merchantId,
    status,
    attempt,
    retakes_left: MAX_PHOTOS - attempt,
    media_id: mediaId,
    document: { type: read.document_type as SlipPrecheck['document']['type'], accepted },
    slots: slots(read),
    checklist: checklist(read),
    gate: { passed: accepted && read.confidence >= SLIP_CONFIDENCE_MIN, confidence: read.confidence, minimum: SLIP_CONFIDENCE_MIN },
    reason,
    guidance: guidanceKey === null ? null : { key: guidanceKey, ...GUIDANCE[guidanceKey] },
    next_action: status === 'READY' ? ACTIONS.CONFIRM_FIELDS : status === 'RETAKE' ? ACTIONS.RETAKE_PHOTO : ACTIONS.SEND_TO_TEAM,
    source: { kind: 'SLIP', label: 'Hospital slip read', ref: `slip:${mediaId}`, as_of: rt.nowIso, origin: 'SIMULATED', clause: 'C3' },
    mode: 'SIMULATED',
    provider: 'mock',
    model: null,
    fallback_reason: 'MOCK_BACKEND',
    attempts: [],
  }
}

/** `read` is what the reader saw (for the doctor question); `consent` the merchant's answer once given. */
export type StoredPrecheck = { view: SlipPrecheck; mediaUrl: string; sample: string | null; confirmed: boolean; read: SlipReading; consent?: { granted: boolean; at: string } }
export type MerchantPrechecks = { photos: number; checks: ReadonlyMap<string, StoredPrecheck> }

const STORES = new WeakMap<MockRuntime, ReadonlyMap<string, MerchantPrechecks>>()

export function prechecksOf(rt: MockRuntime, merchantId: string): MerchantPrechecks {
  return STORES.get(rt)?.get(merchantId) ?? { photos: 0, checks: new Map() }
}

export function savePrechecks(rt: MockRuntime, merchantId: string, next: MerchantPrechecks): void {
  STORES.set(rt, new Map([...(STORES.get(rt) ?? []), [merchantId, next]]))
}

/** The 409 codes of design 2.3 (D9): the screens say a true sentence for each. */
export type ConflictCode = 'no_checkin' | 'photo_limit' | 'already_confirmed' | 'superseded' | 'not_ready' | 'ready_not_team' | 'consent_pending' | 'no_consent_question'

export const conflict = (code: ConflictCode, message: string): MockHttpError => new MockHttpError(code, message, 409)

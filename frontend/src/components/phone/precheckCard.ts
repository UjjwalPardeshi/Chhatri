/**
 * Readers for the two cards a chat message can carry besides the payout card (design 2.6): the slip pre-check card
 * (`card_view`: the pre-check, its checklist sentences and its three actions, each enabled or not) and the doctor
 * question (`consent_for` and its Yes / No). The bubble draws only what these readers accept; anything else is left
 * out, never guessed. The friendly lines of the 409 codes (design 2.11) live here too, in Hindi and English, from the
 * mini-app's copy so both surfaces say the same sentence.
 */
import { ApiError } from '../../api/client'
import { SLIP_SLOT_KEYS, type Message, type SlipSlot } from '../../api/types'
import { t, type CopyKey } from '../../miniapp/lib/copy'

export type CardAction = { kind: string; label_hi: string; label_en: string; enabled: boolean }
export type CardChecklistLine = { id: string; state: 'PASS' | 'WARN'; text_hi: string; text_en: string }
export type PrecheckCard = {
  precheck_id: string
  status: string
  slots: SlipSlot[]
  checklist: CardChecklistLine[]
  actions: CardAction[]
}
export type ConsentCard = { consent_for: string; doctor_name: string | null; hospital_name: string | null; actions: Omit<CardAction, 'enabled'>[] }
export type Bilingual = { hi: string; en: string }

const PRECHECK_ID = /^PC-\d{6,}$/
/** The statuses whose card still waits for the merchant (design 2.3). */
export const OPEN_CARD_STATUSES: readonly string[] = ['READY', 'RETAKE', 'NEEDS_TEAM']

type Json = Record<string, unknown>

const isRecord = (value: unknown): value is Json => typeof value === 'object' && value !== null && !Array.isArray(value)
const isText = (value: unknown): value is string => typeof value === 'string'
const textOrNull = (value: unknown): string | null => (isText(value) ? value : null)

function slotOf(raw: unknown): SlipSlot | null {
  if (!isRecord(raw) || !(SLIP_SLOT_KEYS as readonly unknown[]).includes(raw.key)) return null
  const state = raw.state === 'READ' || raw.state === 'MISSING' || raw.state === 'NOT_ON_SLIP' ? raw.state : null
  if (state === null) return null
  return { key: raw.key as SlipSlot['key'], value: textOrNull(raw.value), state, note: textOrNull(raw.note) }
}

function lineOf(raw: unknown): CardChecklistLine | null {
  if (!isRecord(raw) || !isText(raw.id) || (raw.state !== 'PASS' && raw.state !== 'WARN')) return null
  return { id: raw.id, state: raw.state, text_hi: textOrNull(raw.text_hi) ?? '', text_en: textOrNull(raw.text_en) ?? '' }
}

function actionOf(raw: unknown): CardAction | null {
  if (!isRecord(raw) || !isText(raw.kind) || !isText(raw.label_en)) return null
  return { kind: raw.kind, label_hi: textOrNull(raw.label_hi) ?? '', label_en: raw.label_en, enabled: raw.enabled === true }
}

const listOf = <T,>(raw: unknown, read: (item: unknown) => T | null): T[] => (Array.isArray(raw) ? raw.flatMap((item) => read(item) ?? []) : [])

/** The pre-check card of a chat message (any status), or null when the message carries none. */
export function precheckCardOf(message: Message): PrecheckCard | null {
  const card: unknown = message.card
  if (!isRecord(card) || !isText(card.precheck_id) || !PRECHECK_ID.test(card.precheck_id) || !isText(card.status)) return null
  return { precheck_id: card.precheck_id, status: card.status, slots: listOf(card.slots, slotOf), checklist: listOf(card.checklist, lineOf), actions: listOf(card.actions, actionOf) }
}

/** The doctor question card of a chat message, or null. */
export function consentCardOf(message: Message): ConsentCard | null {
  const card: unknown = message.card
  if (!isRecord(card) || !isText(card.consent_for) || !PRECHECK_ID.test(card.consent_for)) return null
  const actions = listOf(card.actions, actionOf).map(({ kind, label_hi, label_en }) => ({ kind, label_hi, label_en }))
  return { consent_for: card.consent_for, doctor_name: textOrNull(card.doctor_name), hospital_name: textOrNull(card.hospital_name), actions }
}

/** The 409 codes of design 2.3 and the mini-app copy key of each line; anything else is the generic line. */
const CONFLICT_LINES: Readonly<Record<string, CopyKey>> = {
  already_confirmed: 'slip.err.already_confirmed',
  superseded: 'slip.err.superseded',
  consent_pending: 'slip.err.consent_pending',
  photo_limit: 'SLIP_PHOTO_LIMIT',
  no_checkin: 'slip.err.conflict',
  conflict: 'slip.err.conflict',
}

/** Codes after which the question is settled: the buttons go, the line explains why. */
export const SETTLED_CODES: ReadonlySet<string> = new Set(['already_confirmed', 'superseded'])

const bilingual = (key: CopyKey): Bilingual => ({ hi: t(key, 'hi'), en: t(key, 'en') })

/** The friendly line for a failed answer, in Hindi and English. Never the server's own message. */
export function friendlyError(error: unknown): Bilingual {
  const code = error instanceof ApiError ? error.code : ''
  if (code === 'NETWORK_ERROR' || code === 'TIMEOUT') return bilingual('error.network')
  return bilingual(Object.hasOwn(CONFLICT_LINES, code) ? CONFLICT_LINES[code] : 'error.generic')
}

export const DONE_LINE: Bilingual = { hi: t('slip.done', 'hi'), en: t('slip.done', 'en') }

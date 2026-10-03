/**
 * The audit log in plain words (3 Oct): who acted, what happened and which record it touched,
 * written for a person rather than an engineer ("₹1,417 credited to merchant S-0228" instead of
 * `payout.credit`). The raw codes stay in each row's tooltip and in the search, so an auditor
 * loses nothing. Unknown actions fall back to their code with the punctuation taken out.
 */
import type { AuditEntry } from '../../api/types'
import { formatInr } from '../../lib/money'
import { dayLabel, hhmm } from '../../lib/time'

export type Described = { text: string; detail: string | null }
type Data = Readonly<Record<string, unknown>>
type Describer = (data: Data, entry: Pick<AuditEntry, 'subject_id'>) => Described

const ACTORS: Readonly<Record<string, string>> = Object.freeze({
  system: 'Chhatri system',
  'ai-agent': 'Chhatri assistant',
  model: 'Trigger model',
  'policy-engine': 'Policy engine',
  'workflow:payout': 'Payout workflow',
})

const SUBJECTS: Readonly<Record<string, string>> = Object.freeze({
  alert: 'Weather alert',
  ask: 'Question',
  case: 'Case',
  consent: 'Consent',
  cover: 'Cover',
  decision: 'Decision',
  doctor: 'Doctor',
  grievance: 'Complaint',
  holiday_request: 'Instalment holiday request',
  instalment_pause: 'Instalment pause',
  integration: 'Integration',
  media: 'Photo',
  merchant: 'Merchant',
  message: 'Message',
  payout: 'Payout',
  precheck: 'Slip check',
  premium_payment: 'Premium payment',
  quote: 'Price quote',
  replay: 'Replay',
  scenario: 'Replay',
  stt: 'Voice note',
  trigger: 'Trigger',
  workflow: 'Workflow',
  workflow_step: 'Workflow step',
})

const CHANNELS: Readonly<Record<string, string>> = Object.freeze({ SIMULATOR: 'simulated phone', WHATSAPP: 'WhatsApp', TELEGRAM: 'Telegram', SMS: 'SMS', SOUNDBOX: 'Soundbox' })
const OUTCOMES: Readonly<Record<string, string>> = Object.freeze({ APPROVED: 'approved', REFERRED: 'sent to a claims officer', DECLINED: 'declined' })
const REFUSALS: Readonly<Record<string, string>> = Object.freeze({ IN_ARREARS: 'loan in arrears', NO_ALLOWANCE: 'no holidays left this year', NOT_ACTIVE: 'loan not active', FLAG_OFF: 'holidays switched off' })

/** "AREA_PAYOUT_INTRO" or "instalment.holiday_request" -> "area payout intro", "instalment holiday request". */
export function words(code: string): string {
  return code.replace(/[._:-]+/g, ' ').trim().toLowerCase()
}

function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function rupees(value: unknown): string | null {
  return typeof value === 'number' && Number.isSafeInteger(value) ? formatInr(value) : null
}

function merchant(data: Data): string {
  const id = str(data.merchant_id)
  return id ? `merchant ${id}` : 'the merchant'
}

function join(...parts: (string | null)[]): string | null {
  const kept = parts.filter((p): p is string => p !== null && p !== '')
  return kept.length > 0 ? kept.join(' · ') : null
}

function channel(data: Data): string | null {
  const name = str(data.channel)
  return name ? (CHANNELS[name.toUpperCase()] ?? words(name)) : null
}

function penalty(data: Data): string | null {
  if (data.penalty_paise === 0) return 'no penalty'
  const amount = rupees(data.penalty_paise)
  return amount ? `penalty ${amount}` : null
}

/** "the ₹450 instalment" (or "the instalment" when the amount is missing). */
function instalment(data: Data): string {
  const amount = rupees(data.amount_paise)
  return amount ? `the ${amount} instalment` : 'the instalment'
}

function moved(data: Data): string | null {
  const to = str(data.moved_to)
  return to ? `moved to ${words(to)}` : null
}

function decision(kind: string): Describer {
  return (data) => {
    const outcome = str(data.outcome) ?? ''
    const paid = outcome === 'APPROVED' ? rupees(data.amount_paise) : null
    return { text: `${kind} claim ${OUTCOMES[outcome] ?? 'decided'} for ${merchant(data)}`, detail: join(paid ? `pays ${paid}` : null, str(data.referral_reason)) }
  }
}

function sent(data: Data): Described {
  const amount = rupees(data.amount_paise)
  return { text: amount ? `Payout of ${amount} sent to ${merchant(data)}` : `Payout sent to ${merchant(data)}`, detail: str(data.rail) }
}

function credited(data: Data): Described {
  const amount = rupees(data.amount_paise) ?? 'Payout'
  return { text: `${amount} credited to ${merchant(data)}`, detail: str(data.reference) ? `reference ${String(data.reference)}` : null }
}

function holidayAnswer(data: Data): Described {
  const answer = str(data.decision)
  if (answer === 'GRANTED') return { text: `Lender agreed to move the instalment of ${merchant(data)}`, detail: join(moved(data), penalty(data)) }
  if (answer === 'NO_RESPONSE') return { text: `Lender did not answer about the instalment of ${merchant(data)}`, detail: null }
  const reason = str(data.reason_code)
  return { text: `Lender refused to move the instalment of ${merchant(data)}`, detail: reason ? (REFUSALS[reason] ?? words(reason)) : null }
}

const DESCRIBERS: Readonly<Record<string, Describer>> = Object.freeze({
  'scenario.loaded': (data, entry) => ({ text: `Loaded the ${words(entry.subject_id)} replay`, detail: join(str(data.day) ? dayLabel(String(data.day)) : null, str(data.rules_version) ? `rules ${String(data.rules_version)}` : null) }),
  'replay.stopped': () => ({ text: 'Stopped the replay', detail: null }),
  'alert.issued': (data) => ({
    text: `${sentence(words(str(data.level) ?? ''))} ${words(str(data.kind) ?? 'weather')} alert issued`.trim(),
    detail: join(Array.isArray(data.zone_ids) ? `for ${data.zone_ids.join(', ')}` : null, str(data.valid_from) ? `${hhmm(String(data.valid_from))}–${hhmm(str(data.valid_to))}` : null),
  }),
  'trigger.fired': (data) => ({
    text: `Trigger fired in ${str(data.zone_id) ?? 'a zone'}`,
    detail: join(typeof data.index_pct === 'number' ? `sales at ${data.index_pct}% of expected` : null, typeof data.shops_in_index === 'number' ? `${data.shops_in_index} shops` : null),
  }),
  'decision.area': decision('Area'),
  'decision.personal': decision('Personal'),
  'decision.officer': (data) => ({ text: `Claims officer ${OUTCOMES[str(data.outcome) ?? ''] ?? 'decided'} the claim of ${merchant(data)}`, detail: rupees(data.amount_paise) }),
  'claims.area_batch': () => ({ text: 'Decided the area claims', detail: null }),
  'payout.execute': sent,
  'payout.executed': sent,
  'payout.credit': credited,
  'payout.credited': credited,
  'soundbox.announce': (data) => ({ text: `Soundbox announced ${rupees(data.amount_paise) ?? 'the payout'} at ${merchant(data)}`, detail: null }),
  'message.outbound': (data) => ({ text: `Message sent to ${merchant(data)}`, detail: join(channel(data), str(data.key) ? words(String(data.key)) : null) }),
  'message.inbound': (data) => ({ text: `Message received from ${merchant(data)}`, detail: channel(data) }),
  'message.suppressed': (data) => ({ text: `Message to ${merchant(data)} held back`, detail: str(data.reason) ? words(String(data.reason)) : null }),
  'instalment.holiday_request': (data) => ({
    text: `Asked the lender to move ${instalment(data)} of ${merchant(data)}`,
    detail: join(str(data.instalment_date) ? `due ${dayLabel(String(data.instalment_date))}` : null, str(data.loan_id) ? `loan ${String(data.loan_id)}` : null),
  }),
  'instalment.holiday_decision': holidayAnswer,
  'instalment.pause': (data) => ({ text: `Paused ${instalment(data)} of ${merchant(data)}`, detail: join(moved(data), penalty(data)) }),
  'instalment.holiday_skipped': (data) => ({ text: `No instalment holiday asked for ${merchant(data)}`, detail: str(data.reason) ? words(String(data.reason)) : null }),
  'ask.answered': (data) => ({ text: `Answered a question from ${merchant(data)}`, detail: join(str(data.fallback_reason) ? 'safe fallback answer' : 'AI answer', data.handoff ? 'passed to a person' : null) }),
  'intent.detected': (data) => ({ text: `Understood a message from ${merchant(data)}`, detail: str(data.intent) ? words(String(data.intent)) : null }),
  'precheck.shown': (data) => ({ text: `Showed ${merchant(data)} the slip check`, detail: null }),
  'precheck.confirmed': precheckAnswer,
  'slip.read': (data) => ({ text: `Read the hospital slip from ${merchant(data)}`, detail: null }),
  'slip.erased': () => ({ text: 'Deleted the slip photo after reading it', detail: 'privacy' }),
  'voice.transcribed': (data) => ({ text: `Turned a voice note from ${merchant(data)} into text`, detail: null }),
  'voice.confirmed': (data) => ({ text: `${sentence(merchant(data))} confirmed the voice note`, detail: null }),
  'silence.detected': (data) => ({ text: `Noticed ${merchant(data)} stopped selling`, detail: null }),
  'case.open': (data) => ({ text: 'Opened a case for a claims officer', detail: str(data.kind) ? words(String(data.kind)) : null }),
  'case.opened': (data) => ({ text: 'Opened a case for a claims officer', detail: str(data.kind) ? words(String(data.kind)) : null }),
  'case.resolve': (data) => ({ text: 'Claims officer closed the case', detail: str(data.outcome) ? words(String(data.outcome)) : null }),
  'grievance.open': (data) => ({ text: `Complaint opened by ${merchant(data)}`, detail: null }),
  'grievance.escalate': (data) => ({ text: `Complaint of ${merchant(data)} escalated`, detail: null }),
  'grievance.resolve': (data) => ({ text: `Complaint of ${merchant(data)} resolved`, detail: null }),
  'consent.granted': (data) => ({ text: `${sentence(merchant(data))} gave consent`, detail: str(data.purpose) ? words(String(data.purpose)) : null }),
  'consent.refused': (data) => ({ text: `${sentence(merchant(data))} said no`, detail: str(data.purpose) ? words(String(data.purpose)) : null }),
  'consent.withdrawn': (data) => ({ text: `${sentence(merchant(data))} withdrew consent`, detail: str(data.purpose) ? words(String(data.purpose)) : null }),
  'cover.quoted': (data) => ({ text: `Quoted a cover price for ${merchant(data)}`, detail: null }),
  'cover.cancelled': (data) => ({ text: `Cover of ${merchant(data)} cancelled`, detail: null }),
  'premium.link_created': (data) => ({ text: `Sent a premium payment link to ${merchant(data)}`, detail: null }),
  'premium.paid': (data) => ({ text: `Premium paid by ${merchant(data)}`, detail: rupees(data.amount_paise) }),
  'premium.not_settled': (data) => ({ text: `Premium not collected from ${merchant(data)}`, detail: null }),
  'premium.link_failed': (data) => ({ text: `Premium payment link failed for ${merchant(data)}`, detail: null }),
  'workflow.step_failed': () => ({ text: 'A workflow step failed and will retry', detail: null }),
  'workflow.start_failed': () => ({ text: 'A workflow could not start', detail: null }),
  'channel.preference_set': (data) => ({ text: `${sentence(merchant(data))} now gets messages on ${channel(data) ?? 'a new app'}`, detail: null }),
  'integration.fallback_set': (data, entry) => ({ text: data.forced ? `Switched ${words(entry.subject_id)} to its fallback` : `Put ${words(entry.subject_id)} back on its normal mode`, detail: null }),
  'telegram.bound': (data) => ({ text: `Linked a Telegram chat to ${merchant(data)}`, detail: null }),
  'telegram.unbound': (data) => ({ text: `Unlinked the Telegram chat of ${merchant(data)}`, detail: null }),
  'doctor.asked': (data) => ({ text: 'Asked the treating doctor to confirm the visit', detail: str(data.doctor_registration_no) ? String(data.doctor_registration_no) : null }),
  'doctor.answered': (data) => ({ text: 'The treating doctor answered', detail: str(data.status) ? words(String(data.status)) : null }),
  'doctor.enrolled': (data) => ({ text: "Linked a doctor's Telegram chat", detail: str(data.registration_no) ? String(data.registration_no) : null }),
  'doctor.unenrolled': (data) => ({ text: "Unlinked a doctor's Telegram chat", detail: str(data.registration_no) ? String(data.registration_no) : null }),
  'doctor.enrolment_reset': (data) => ({ text: 'Made a new doctor enrolment link', detail: str(data.registration_no) ? String(data.registration_no) : null }),
})

/** The merchant's answer to the slip check (design 2.3): confirm, the doctor question, or the team. */
function precheckAnswer(data: Readonly<Record<string, unknown>>): Described {
  const who = sentence(merchant(data))
  switch (data.action) {
    case 'CONSENT_YES':
      return { text: `${who} agreed that we may ask the doctor`, detail: null }
    case 'CONSENT_NO':
      return { text: `${who} said no to asking the doctor`, detail: null }
    case 'SEND_TO_TEAM':
      return { text: `${who} sent the slip to the team`, detail: null }
    default:
      return { text: `${who} confirmed the slip details`, detail: data.awaiting_consent ? 'asked about the doctor next' : null }
  }
}

/** Who acted, in words: "Payout workflow", "Chhatri assistant", "Claims officer", "Merchant S-0142". */
export function actorLabel(actor: string): string {
  const known = ACTORS[actor]
  if (known) return known
  const [kind, id] = actor.split(':', 2)
  if (kind === 'officer') return 'Claims officer'
  if (kind === 'merchant') return id ? `Merchant ${id}` : 'Merchant'
  if (kind === 'lender') return 'Lender'
  if (kind === 'doctor') return id ? `Doctor ${id}` : 'Doctor'
  return sentence(words(actor))
}

/** What happened, in words, with a short detail line (amounts, places, reasons) when the entry has one. */
export function describeEntry(entry: Pick<AuditEntry, 'action' | 'data' | 'subject_id'>): Described {
  const describe = DESCRIBERS[entry.action]
  return describe ? describe(entry.data, entry) : { text: sentence(words(entry.action)), detail: null }
}

/** The record an entry touched: "Instalment pause" for `instalment_pause`. */
export function subjectLabel(subjectType: string): string {
  return SUBJECTS[subjectType] ?? sentence(words(subjectType))
}

/** Everything a search can match: the words on screen and the raw codes behind them. */
export function searchText(entry: AuditEntry): string {
  const { text, detail } = describeEntry(entry)
  return [entry.action, entry.actor, entry.subject_type, entry.subject_id, actorLabel(entry.actor), text, detail ?? '', subjectLabel(entry.subject_type)].join(' ').toLowerCase()
}

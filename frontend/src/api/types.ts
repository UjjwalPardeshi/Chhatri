/**
 * HTTP API shapes — a field-for-field mirror of SPEC §19.2 (and the SSE events of §19.1).
 * Money fields end in `_paise` and always travel with a preformatted `*_label` (SPEC §4.2), so the
 * console never re-derives money. Keep this file in lock-step with `chhatri/api/schemas.py`.
 */
import type { FeatureCollection } from 'geojson'

export type ApiErrorBody = { code: string; message: string; fields?: Record<string, string> }
export type ListMeta = { total: number; limit: number; offset: number }
export type Envelope<T> = { ok: true; data: T; meta?: ListMeta } | { ok: false; error: ApiErrorBody }

export const INTEGRATION_NAMES = [
  'sarvam_stt',
  'sarvam_tts',
  'sarvam_chat',
  'sarvam_vision',
  'whatsapp',
  'paytm',
  'n8n',
  'memory',
  'weather',
  'soundbox',
  'sales_data',
  'alerts',
  'payout_rail',
  'lender',
  'kyc',
  'gemini_chat',
  'gemini_vision',
] as const
export type IntegrationName = (typeof INTEGRATION_NAMES)[number]
export type IntegrationMode = 'LIVE' | 'SIMULATED' | 'FALLBACK'
/** The last call a live adapter made (fs-08 9.3); null until one was made. */
export type IntegrationLastCall = { at: string; outcome: string; ms: number | null }
/**
 * One row of GET /api/integrations and the answer of POST /api/integrations/{component}/fallback (fs-08 9.3).
 * The X6 fields are optional so a row from a server without the flag still parses.
 */
export type IntegrationStatus = {
  name: IntegrationName
  mode: IntegrationMode
  detail: string
  provider?: string | null
  model?: string | null
  fallback_reason?: string | null
  switchable?: boolean
  forced?: boolean
  last_call?: IntegrationLastCall | null
}

export const SCENARIO_NAMES = ['monsoon', 'illness', 'illness_mismatch', 'buy_cover'] as const
export type ScenarioName = (typeof SCENARIO_NAMES)[number]

export type ClockState = {
  now: string
  scenario: ScenarioName | null
  scenario_title: string
  running: boolean
  speed: number
  start: string
  end: string
  label: string
}

export type ZoneStatusName = 'normal' | 'watch' | 'triggered' | 'slow_day' | 'no_data'
export type AlertLevel = 'YELLOW' | 'ORANGE' | 'RED'
export type AlertKind = 'RAIN' | 'CIVIC' | 'HEATWAVE'

export type ZoneAlert = {
  id: string
  level: AlertLevel
  kind: AlertKind
  valid_from: string
  valid_to: string
  headline_en: string
}

export type ZoneSnapshot = {
  zone_id: string
  ward: string
  name: string
  shops: number
  index_pct: number | null
  live_index_pct: number | null
  lower_bound_pct: number
  status: ZoneStatusName
  hours_below: number
  alert: ZoneAlert | null
  label: string
}

export type Kpis = {
  zones_triggered: number
  shops_paid: number
  trigger_to_money_min: number | null
  total_paid_paise: number
  total_paid_label: string
  instalments_paused: number
}

export type FeedItem = {
  id: number
  at: string
  type: string
  text_en: string
  zone_id?: string
  merchant_id?: string
}

export type StateSnapshot = {
  clock: ClockState
  zones: ZoneSnapshot[]
  hexes: Record<string, number | null>
  kpis: Kpis
  triggers: AreaTrigger[]
  explanations: Record<string, string>
  feed: FeedItem[]
  demo_merchant_id: string | null
  rain_band: FeatureCollection | null
}

export type Alert = {
  id: string
  kind: AlertKind
  level: AlertLevel
  zone_ids: string[]
  issued_at: string
  valid_from: string
  valid_to: string
  source: string
  headline_en: string
  headline_hi: string
}

export type InstalmentPause = {
  id: string
  loan_id: string
  merchant_id: string
  instalment_date: string
  amount_paise: number
  amount_label: string
  reason: string
  decision_id: string
  created_at: string
}

export type AreaTrigger = {
  id: string
  zone_id: string
  alert_id: string
  window_start: string
  window_end: string
  index_pct: number
  drop_pct: number
  hourly_index_pct: number[]
  lower_bound_pct: number
  shops_in_index: number
  fired_at: string
}

export type ZonePanelRowLabel = 'Alert' | 'Sales' | 'Cover' | 'Paid' | 'Total'
export type ZonePanel = {
  zone: ZoneSnapshot
  triggered: boolean
  rows: { label: ZonePanelRowLabel; value: string }[]
  explanation: string | null
  shops_paid: number
  total_paid_paise: number
  total_paid_label: string
  hourly: { hour: string; index_pct: number | null }[]
}

export type CheckStatus = 'PASS' | 'FAIL' | 'UNSURE' | 'NOT_APPLICABLE' | 'WAIVED_BY_OFFICER'
export type Severity = 'HARD' | 'SOFT'
export type Check = {
  code: string
  status: CheckStatus
  severity: Severity
  label_en: string
  detail_en: string
  observed: string | null
  required: string | null
}

export type Explanation = {
  weekday_en: string
  weekday_hi: string
  expected_day_paise: number
  expected_day_label: string
  drop_pct: number | null
  share_pct: number
  days: number
  cap_paise: number
  capped: boolean
  amount_paise: number
  amount_label: string
  formula_en: string
  formula_hi: string
}

export type DecisionOutcome = 'APPROVED' | 'REFERRED' | 'DECLINED'
export type Decision = {
  id: string
  claim_id: string
  merchant_id: string
  outcome: DecisionOutcome
  amount_paise: number
  amount_label: string
  checks: Check[]
  rules_version: string
  decided_at: string
  decided_by: string
  explanation: Explanation | null
  referral_reason: string | null
  supersedes: string | null
}

export type PayoutStatus = 'PENDING' | 'CREDITED' | 'FAILED'
export type Payout = {
  id: string
  decision_id: string
  merchant_id: string
  amount_paise: number
  amount_label: string
  status: PayoutStatus
  rail: string
  created_at: string
  credited_at: string | null
  reference: string
}

export type MerchantSummary = {
  id: string
  shop_name: string
  owner_name: string
  zone_id: string
  shop_type: string
  lat: number
  lng: number
  is_demo: boolean
  covered: boolean
}

export type MerchantDetail = MerchantSummary & {
  owner_name_hi: string
  kyc_name_masked: string
  phone_masked: string
  language: string
  cover: { status: string; starts_on: string; prepaid_through: string | null; premium_per_day_label: string } | null
  loan: { daily_instalment_label: string; lender_name: string } | null
  expected_today_label: string | null
  payouts: Payout[]
  decisions: Decision[]
  /** Every EDI holiday request with the lender's answer (X4, data-model 5.12); `[]` while x4_lender_request is off. */
  holiday_requests: HolidayRequest[]
}

/** One EDI holiday request and the lender's answer, whatever the outcome (X4, fs-03 section 7.5). Grants also have a pause. */
export type HolidayRequest = {
  id: string
  loan_id: string
  decision_id: string
  payout_id: string
  instalment_date: string
  instalment_paise: number
  instalment_label: string
  requested_at: string
  status: HolidayStatus
  reason_code: LenderReasonCode | null
  decided_at: string | null
  lender: string
}

export type MessageDirection = 'INBOUND' | 'OUTBOUND'
export type MessageChannel = 'WHATSAPP' | 'SIMULATOR' | 'SOUNDBOX'
export type MessageKind = 'TEXT' | 'VOICE' | 'IMAGE' | 'PAYOUT_CARD' | 'CASE_CHIP' | 'SOUNDBOX' | 'TEMPLATE' | 'BUTTONS'
export type PayoutCard = {
  amount_label: string
  subtitle_hi: string
  subtitle_en: string
  badge: string
  footer_en?: string
}
export type MessageMeta = {
  transcript?: string
  voice_source?: 'sarvam' | 'browser-simulated'
  duration_s?: number
  case_id?: string
  /** H26 label of a message that came from the model path (fs-05 section 10); absent for engine messages. */
  mode?: 'LIVE' | 'SIMULATED' | 'FALLBACK'
  provider?: string
  model?: string | null
  fallback_reason?: string | null
}
export type Message = {
  id: string
  merchant_id: string
  direction: MessageDirection
  channel: MessageChannel
  kind: MessageKind
  text_hi: string | null
  text_en: string | null
  audio_url: string | null
  media_url: string | null
  card: PayoutCard | null
  created_at: string
  meta: MessageMeta
}

export type CaseKind = 'PERSONAL_CLAIM_REVIEW' | 'DISPUTE' | 'AREA_REVIEW'
export type CaseStatus = 'OPEN' | 'APPROVED' | 'DECLINED' | 'CLOSED'
export type SlipEvidence = {
  media_url: string
  patient_name: string | null
  admission_date: string | null
  discharge_date: string | null
  hospital_name: string | null
  document_type: string | null
  confidence: number
  source: string
  /** H26 label of the slip reader, when the server sends it. */
  mode?: 'LIVE' | 'SIMULATED' | 'FALLBACK'
  provider?: string
  model?: string | null
  fallback_reason?: string | null
}
export type CaseEvidence = {
  expected_vs_actual?: { hour: string; expected_paise: number; actual_paise: number }[]
  slip?: SlipEvidence
  kyc_name?: string
  name_score?: number
  silent_days?: string[]
  merchant_text?: string
  precedents?: { subject_id: string; kind: string; at: string; text: string }[]
}
export type Case = {
  id: string
  kind: CaseKind
  merchant_id: string
  merchant_name: string
  status: CaseStatus
  opened_at: string
  due_by: string
  summary_en: string
  decision: Decision | null
  evidence: CaseEvidence
  resolution: string | null
  resolved_by: string | null
  resolved_at: string | null
}

/** POST /api/cases/{id}/approve and /decline (SPEC §19): the officer's decision and the resolved case. */
export type OfficerResult = { decision: Decision; case: Case }

export type AuditEntry = {
  seq: number
  at: string
  recorded_at: string
  actor: string
  action: string
  subject_type: string
  subject_id: string
  data: Record<string, unknown>
  prev_hash: string
  hash: string
}
export type AuditVerify = { valid: boolean; entries: number; head_hash: string; first_bad_seq: number | null }

export type PolicyView = {
  rules: Record<string, unknown>
  authority: { case: string; alone: string; human: string }[]
  checks: { code: string; severity: Severity; applies: 'area' | 'personal' | 'all'; passes_when: string }[]
}

export type BacktestTrigger = {
  name: 'chhatri' | 'weather_only'
  real_drops: number
  real_drops_paid: number
  recall: number
  payouts: number
  payouts_no_real_drop: number
  false_positive_rate: number
  paid_paise: number
  trigger_to_money: string
  documents_per_area_claim: number
}
export type BacktestZone = {
  zone_id: string
  premium_per_day_label: string
  premiums_paise: number
  payouts_paise: number
  loss_ratio: number
  chhatri_fp: number
  chhatri_fn: number
}
export type BacktestReport = {
  label: string
  seasons: string[]
  generated_at: string
  triggers: BacktestTrigger[]
  zones: BacktestZone[]
  personal: { claims: number; auto_paid: number; referred: number; referred_share: number }
  notes: string[]
}

/** GET /api/health, /api/session, /api/preflight (SPEC §19). `features`: the sorted names of the flags that are on. */
export type Health = { status: string; version: string; seed: number; features: string[] }
export type Session = { officer_token: string }
export type PreflightItem = { name: string; ok: boolean; detail: string }

/** SSE `soundbox` payload (SPEC §19.1). */
export type SoundboxEvent = { merchant_id: string; text: string; amount_label: string; audio_url: string | null }
/** SSE `audit` payload (SPEC §19.1). */
export type AuditEvent = { seq: number; action: string; actor: string; subject_type: string; subject_id: string }

/** SPEC §19.1: event type → `data` payload. */
export type SseEventMap = {
  scenario: { clock: ClockState }
  tick: { clock: ClockState }
  zone: { zone: ZoneSnapshot }
  hexes: { hexes: Record<string, number | null> }
  alert: { alert: Alert }
  trigger: { trigger: AreaTrigger }
  decision: { decision: Decision }
  payout: { payout: Payout }
  instalment: { pause: InstalmentPause }
  message: { message: Message }
  soundbox: SoundboxEvent
  case: { case: Case }
  audit: AuditEvent
  kpis: { kpis: Kpis }
}
export type SseEventType = keyof SseEventMap
export const SSE_EVENT_TYPES: readonly SseEventType[] = [
  'scenario',
  'tick',
  'zone',
  'hexes',
  'alert',
  'trigger',
  'decision',
  'payout',
  'instalment',
  'message',
  'soundbox',
  'case',
  'audit',
  'kpis',
]
export type SseEvent = {
  [K in SseEventType]: { id: string; type: K; at: string; data: SseEventMap[K] }
}[SseEventType]
export type SseEventOf<K extends SseEventType> = Extract<SseEvent, { type: K }>

/** Demo voice notes (SPEC §19 POST /voice-demo). */
export type VoiceDemoKey = 'why' | 'dispute' | 'ill' | 'cover'

/**
 * The merchant mini-app routes (data-model section 5.1 and 5.8, fs-04 section 6.2). Read-only routes without a flag,
 * so the console's case panel can read the same receipt (card 6.1). The strict parsers that reject an unknown field
 * or an impossible combination live in `miniapp/api/parse.ts`; these are the shapes they return.
 */
export const COVER_STATUSES = ['NONE', 'PENDING_PAYMENT', 'WAITING', 'ACTIVE', 'LAPSED', 'CANCELLED'] as const
export type CoverStatus = (typeof COVER_STATUSES)[number]

/** GET /api/merchants/{id}/cover. `NONE` is an API value only; a merchant with no cover gets nulls for dates and amounts. */
export type Cover = {
  merchant_id: string
  cover_id: string | null
  status: CoverStatus
  status_text_hi: string
  status_text_en: string
  zone_id: string
  zone_name: string
  purchased_at: string | null
  starts_on: string | null
  prepaid_through: string | null
  waiting_period_days: number
  premium_per_day_paise: number
  premium_per_day_label: string
  premium_due: boolean
  annual_limit_paise: number | null
  annual_limit_label: string | null
  amount_claimed_paise: number | null
  amount_claimed_label: string | null
  amount_remaining_paise: number | null
  amount_remaining_label: string | null
  alert_active: boolean
  alert_id: string | null
}

export const CLAIM_KINDS = ['AREA', 'PERSONAL', 'DISPUTE'] as const
export type ClaimKind = (typeof CLAIM_KINDS)[number]
export const STEP_NAMES = ['Detected', 'Checked', 'Decided', 'Paid', 'EDI holiday'] as const
export type StepName = (typeof STEP_NAMES)[number]
export const STEP_STATUSES = ['completed', 'current', 'pending', 'skipped'] as const
export type StepStatus = (typeof STEP_STATUSES)[number]
export const LENDER_REASON_CODES = ['FLAG_OFF', 'NOT_ACTIVE', 'IN_ARREARS', 'NO_ALLOWANCE'] as const
export type LenderReasonCode = (typeof LENDER_REASON_CODES)[number]
export type EdiResult = 'GRANTED' | 'REFUSED' | 'NO_LOAN' | 'NO_RESPONSE'

export type ClaimStep = {
  name: StepName
  status: StepStatus
  /** Decided: APPROVED, REFERRED or DECLINED. EDI holiday: GRANTED, REFUSED, NO_LOAN or NO_RESPONSE. Null elsewhere. */
  result: DecisionOutcome | EdiResult | null
  at: string | null
  reason_hi: string | null
  reason_en: string | null
  /** Set only when the lender refuses. The merchant never sees it; the console does. */
  reason_code: LenderReasonCode | null
}

/** GET /api/merchants/{id}/claims: one item per claim and one per dispute, newest first. */
export type ClaimItem = {
  claim_id: string | null
  disputed_claim_id: string | null
  kind: ClaimKind
  claim_at: string
  zone_id: string | null
  trigger_id: string | null
  decision_id: string | null
  outcome: DecisionOutcome | null
  amount_paise: number | null
  amount_label: string | null
  steps: ClaimStep[]
  case_id: string | null
  case_status: CaseStatus | null
  due_by: string | null
  resolution: string | null
}

export const SOURCE_KINDS = [
  'RULES',
  'CLAUSE',
  'ALERT',
  'SALES_INDEX',
  'FORECAST',
  'ZONE_BOUND',
  'COVER',
  'PREMIUM',
  'KYC',
  'SLIP',
  'SALES_DAY',
  'PAYOUT_HISTORY',
  'LENDER',
] as const
export type SourceKind = (typeof SOURCE_KINDS)[number]
export type SourceOrigin = 'LIVE' | 'SIMULATED' | 'CONFIG'

/** The closed Source object (H13): exactly these six fields. The chip says "Source", never "verified by". */
export type Source = {
  kind: SourceKind
  label: string
  ref: string
  as_of: string | null
  origin: SourceOrigin
  clause: string | null
}

export type ReceiptDecision = {
  id: string
  claim_id: string
  merchant_id: string
  outcome: DecisionOutcome
  amount_paise: number
  amount_label: string
  rules_version: string
  decided_at: string
  decided_by: string
  supersedes: string | null
  referral_reason: string | null
}

export type ReceiptFact = { key: string; label_en: string; value: string; sources: Source[] }
export type ReceiptExplanation = { formula_en: string; formula_hi: string; clause: string; facts: ReceiptFact[] }

export type ReceiptCheck = {
  code: string
  severity: Severity
  status: CheckStatus
  label_en: string
  detail_en: string
  observed: string | null
  required: string | null
  clause: string | null
  /** True on the slip checks after the merchant erased the slip (Wave 3). Sent from the first release. */
  erased: boolean
  sources: Source[]
}

export const COUNTERFACTUAL_KINDS = ['FLIP_FROM_DECLINED', 'FLIP_FROM_REFERRED', 'AMOUNT_SENSITIVITY', 'ZONE_NO_TRIGGER', 'EXPLAIN_ONLY'] as const
export type CounterfactualKind = (typeof COUNTERFACTUAL_KINDS)[number]
export type CounterfactualChange = { check_code: string | null; field: string; observed: string; needed: string }
export type CounterfactualResult = { outcome: DecisionOutcome; amount_paise: number; amount_label: string }

/** Produced by re-running the real engine on a changed copy of the facts; `verified` is always true. */
export type Counterfactual = {
  id: string
  kind: CounterfactualKind
  actionable: boolean
  changes: CounterfactualChange[]
  result: CounterfactualResult | null
  verified: true
  text_en: string
  text_hi: string
  sources: Source[]
}

export type ReceiptPayout = { id: string; status: PayoutStatus; amount_label: string; credited_at: string | null }
export type HolidayStatus = 'REQUESTED' | 'GRANTED' | 'REFUSED' | 'NO_RESPONSE'
export type ReceiptEdi = {
  request_id: string
  status: HolidayStatus
  reason_code: LenderReasonCode | null
  instalment_date: string
  instalment_label: string
  decided_at: string | null
  lender: string
}
export type ReceiptCase = { id: string; kind: CaseKind; status: CaseStatus; due_by: string }
export type ReceiptAudit = { seq: number; hash_short: string; verify_path: string }
export type ReceiptGrievance = { dispute_allowed: boolean; ladder: string[]; first_step_hours: number }

/** GET /api/decisions/{decision_id}/receipt. */
export type Receipt = {
  decision: ReceiptDecision
  explanation: ReceiptExplanation
  checks: ReceiptCheck[]
  counterfactuals: Counterfactual[]
  payout: ReceiptPayout | null
  edi: ReceiptEdi | null
  case: ReceiptCase | null
  audit: ReceiptAudit
  grievance: ReceiptGrievance
}

/** POST /api/premium/link (officer token): the quote is OK or BLOCKED, never "approved". */
export type CoverQuote = {
  id: string
  merchant_id: string
  outcome: 'OK' | 'BLOCKED'
  requested_at: string
  starts_on: string
  premium_per_day_paise: number
  premium_per_day_label: string
  first_payment_paise: number
  first_payment_label: string
  days_prepaid: number
  reason_en: string
  reason_hi: string
  blocking_alert_id: string | null
}
export type PremiumPayment = {
  id: string
  merchant_id: string
  amount_paise: number
  amount_label: string
  method: 'SETTLEMENT_DEDUCTION' | 'PAYMENT_LINK'
  covers_from: string
  covers_to: string
  status: 'PENDING' | 'PAID' | 'FAILED' | 'EXPIRED'
  link_id: string | null
  link_url: string | null
  /** Where the link came from ("simulated" for the free simulator). */
  source: string
  created_at: string
  paid_at: string | null
}
export type PremiumLinkResult = { quote: CoverQuote; premium: PremiumPayment | null }

/** POST /api/webhooks/paytm answers `paid`, `ignored` or `duplicate`. */
export type PaytmAck = { status: 'paid' | 'ignored' | 'duplicate'; link_id: string }

/** N3 slip pre-check (data-model 5.3, card 4.2). */
export const PRECHECK_STATUSES = ['READY', 'RETAKE', 'NEEDS_TEAM', 'SUPERSEDED', 'CONFIRMED'] as const
export type PrecheckStatus = (typeof PRECHECK_STATUSES)[number]
export const PRECHECK_REASONS = ['READ_FAILED', 'INJECTION_SUSPECTED', 'NOT_A_HOSPITAL_DOCUMENT', 'LOW_CONFIDENCE', 'NAME_MISSING', 'DATES_NOT_CLEAR'] as const
export type PrecheckReason = (typeof PRECHECK_REASONS)[number]
export const SLIP_SLOT_KEYS = ['patient_name', 'admission_date', 'discharge_date', 'hospital_name'] as const
export type SlipSlotKey = (typeof SLIP_SLOT_KEYS)[number]
export type SlipSlot = { key: SlipSlotKey; value: string | null; state: 'READ' | 'MISSING' | 'NOT_ON_SLIP'; note: string | null }
export const SLIP_CHECKLIST_IDS = ['photo_readable', 'name_on_slip', 'dates_on_slip'] as const
export type SlipChecklistId = (typeof SLIP_CHECKLIST_IDS)[number]
export type SlipChecklistLine = { id: SlipChecklistId; state: 'PASS' | 'WARN' }
export const PRECHECK_GUIDANCE_KEYS = ['SLIP_RETAKE_CLEAR', 'SLIP_RETAKE_DOCUMENT', 'SLIP_RETAKE_NAME', 'SLIP_RETAKE_DATE', 'SLIP_NO_READ', 'SLIP_PHOTO_LIMIT'] as const
export type PrecheckGuidanceKey = (typeof PRECHECK_GUIDANCE_KEYS)[number]
export const PRECHECK_ACTION_KINDS = ['CONFIRM_FIELDS', 'RETAKE_PHOTO', 'SEND_TO_TEAM'] as const
export type PrecheckActionKind = (typeof PRECHECK_ACTION_KINDS)[number]
export type PrecheckAttempt = { provider: string; outcome: string; ms: number }
export type SlipPrecheck = {
  precheck_id: string
  merchant_id: string
  status: PrecheckStatus
  attempt: number
  retakes_left: number
  media_id: string
  document: { type: 'admission_slip' | 'discharge_summary' | 'prescription' | 'bill' | 'other' | null; accepted: boolean }
  slots: SlipSlot[]
  checklist: SlipChecklistLine[]
  /** For the console and the officer only; the merchant screens never show it. */
  gate: { passed: boolean; confidence: number; minimum: number }
  reason: PrecheckReason | null
  guidance: { key: PrecheckGuidanceKey; text_hi: string; text_en: string } | null
  next_action: { kind: PrecheckActionKind; label_hi: string; label_en: string }
  source: Source
  mode: 'LIVE' | 'SIMULATED' | 'FALLBACK'
  provider: 'gemini' | 'sarvam' | 'simulated' | 'mock' | 'none'
  model: string | null
  fallback_reason: string | null
  attempts: PrecheckAttempt[]
}
export type PrecheckAction = 'CONFIRM' | 'SEND_TO_TEAM'
export type PrecheckConfirm = {
  precheck_id: string
  status: 'CONFIRMED'
  confirmed_as: 'FIELDS_CONFIRMED' | 'SENT_TO_TEAM'
  claim_id: string
  decision_id: string
  outcome: 'APPROVED' | 'REFERRED' | 'DECLINED'
  case_id: string | null
  messages: Message[]
}
/** The body of the pre-check route: a photo goes as a form, a sample slip as JSON. */
/** No `sample` means the loaded scenario's own sample slip (data-model 5.3). */
/** `consent` and `notice_version`: the merchant's OK to read a slip, sent when no slip consent is ACTIVE (n6_consents, fs-07 9.3). */
export type PrecheckConsent = { consent?: true; notice_version?: string }
export type PrecheckInput = ({ file: File; lang?: 'hi' | 'en' } | { sample?: string; lang?: 'hi' | 'en' }) & PrecheckConsent

/** H8 ops strip and H24 what-if (cards 6.2 and 6.3): defined with their parsers in opsWhatIf.ts. */
export type { OpsSummary, OpsHolidayCounts, WhatIfArea, WhatIfRequest, WhatIfOverrides } from './opsWhatIf'

/** N5, N6 and H25 (data-model 5.4, 5.5 and 5.10): the types live beside their strict parsers and are re-exported here. */
export type { ActivityItem, Consent, ForgetResult, Grievance, LadderStep, WithdrawResult } from '../miniapp/api/rights'
export type { EvalMetric, EvalsSummary, EvalSuite } from './evals'

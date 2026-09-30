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
] as const
export type IntegrationName = (typeof INTEGRATION_NAMES)[number]
export type IntegrationMode = 'LIVE' | 'SIMULATED'
export type IntegrationStatus = { name: IntegrationName; mode: IntegrationMode; detail: string }

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

/** GET /api/health, /api/session, /api/preflight (SPEC §19). */
export type Health = { status: string; version: string; seed: number }
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

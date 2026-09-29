/**
 * API Types - mirrored from SPEC §19.2
 * TypeScript types for all Chhatri API responses
 */

// Envelope types
export interface Envelope<T> {
  ok: true
  data: T
  meta?: {
    total: number
    limit: number
    offset: number
  }
}

export interface ErrorEnvelope {
  ok: false
  error: {
    code: string
    message: string
    fields?: Record<string, string>
  }
}

export type ApiResponse<T> = Envelope<T> | ErrorEnvelope

// Integration status
export type IntegrationName =
  | 'sarvam_stt'
  | 'sarvam_tts'
  | 'sarvam_chat'
  | 'sarvam_vision'
  | 'whatsapp'
  | 'paytm'
  | 'n8n'
  | 'memory'
  | 'weather'
  | 'soundbox'
  | 'sales_data'
  | 'alerts'
  | 'payout_rail'
  | 'lender'
  | 'kyc'

export interface IntegrationStatus {
  name: IntegrationName
  mode: 'LIVE' | 'SIMULATED'
  detail: string
}

// Clock and scenario
export type ScenarioName = 'monsoon' | 'illness' | 'illness_mismatch' | 'buy_cover'

export interface ClockState {
  now: string // ISO IST
  scenario: ScenarioName | null
  scenario_title: string
  running: boolean
  speed: number // sim minutes per real second
  start: string
  end: string
  label: string // e.g. "Mumbai · monsoon replay · 17:00 · simulated"
}

// Zones and hexes
export type ZoneStatusName = 'normal' | 'watch' | 'triggered' | 'slow_day' | 'no_data'

export interface AlertSnap {
  id: string
  level: 'YELLOW' | 'ORANGE' | 'RED'
  kind: 'RAIN' | 'CIVIC' | 'HEATWAVE'
  valid_from: string
  valid_to: string
  headline_en: string
}

export interface ZoneSnapshot {
  zone_id: string
  ward: string
  name: string
  shops: number
  index_pct: number | null
  live_index_pct: number | null
  lower_bound_pct: number
  status: ZoneStatusName
  hours_below: number
  alert: AlertSnap | null
  label: string // "Z7 · 37% · 46 shops"
}

// KPIs
export interface Kpis {
  zones_triggered: number
  shops_paid: number
  trigger_to_money_min: number | null
  total_paid_paise: number
  total_paid_label: string
  instalments_paused: number
}

// Feed
export interface FeedItem {
  id: number
  at: string
  type: string
  text_en: string
  zone_id?: string
  merchant_id?: string
}

// Full state snapshot
export interface StateSnapshot {
  clock: ClockState
  zones: ZoneSnapshot[]
  hexes: Record<string, number | null> // h3 → index_pct or null
  kpis: Kpis
  triggers: AreaTrigger[]
  explanations: Record<string, string> // zone_id → explanation text
  feed: FeedItem[]
  demo_merchant_id: string | null
  rain_band: Record<string, unknown> | null // GeoJSON FeatureCollection
}

// Alert
export interface Alert {
  id: string
  kind: 'RAIN' | 'CIVIC' | 'HEATWAVE'
  level: 'YELLOW' | 'ORANGE' | 'RED'
  zone_ids: string[]
  issued_at: string
  valid_from: string
  valid_to: string
  source: string
  headline_en: string
  headline_hi: string
}

// Instalment pause
export interface InstalmentPause {
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

// Area trigger
export interface AreaTrigger {
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

// Zone panel (detailed zone view)
export interface ZonePanelRow {
  label: 'Alert' | 'Sales' | 'Cover' | 'Paid' | 'Total'
  value: string
}

export interface ZoneHourly {
  hour: string
  index_pct: number | null
}

export interface ZonePanel {
  zone: ZoneSnapshot
  triggered: boolean
  rows: ZonePanelRow[]
  explanation: string | null
  shops_paid: number
  total_paid_paise: number
  total_paid_label: string
  hourly: ZoneHourly[]
}

// Policy/Decision types
export type CheckStatus = 'PASS' | 'FAIL' | 'UNSURE' | 'NOT_APPLICABLE' | 'WAIVED_BY_OFFICER'
export type CheckSeverity = 'HARD' | 'SOFT'

export interface Check {
  code: string
  status: CheckStatus
  severity: CheckSeverity
  label_en: string
  detail_en: string
  observed: string | null
  required: string | null
}

export interface Explanation {
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

export interface Decision {
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

export interface Payout {
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

// Merchant types
export interface MerchantSummary {
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

export interface MerchantCover {
  status: string
  starts_on: string
  prepaid_through: string | null
  premium_per_day_label: string
}

export interface MerchantLoan {
  daily_instalment_label: string
  lender_name: string
}

export interface MerchantDetail extends MerchantSummary {
  owner_name_hi: string
  kyc_name_masked: string
  phone_masked: string
  language: string
  cover: MerchantCover | null
  loan: MerchantLoan | null
  expected_today_label: string | null
  payouts: Payout[]
  decisions: Decision[]
}

// Messages
export type MessageDirection = 'INBOUND' | 'OUTBOUND'
export type MessageChannel = 'WHATSAPP' | 'SIMULATOR' | 'SOUNDBOX'
export type MessageKind = 'TEXT' | 'VOICE' | 'IMAGE' | 'PAYOUT_CARD' | 'CASE_CHIP' | 'SOUNDBOX' | 'TEMPLATE' | 'BUTTONS'

export interface MessageCard {
  amount_label: string
  subtitle_hi: string
  subtitle_en: string
  badge: string
  footer_en?: string
}

export interface MessageMeta {
  transcript?: string
  voice_source?: 'sarvam' | 'browser-simulated'
  duration_s?: number
  case_id?: string
}

export interface Message {
  id: string
  merchant_id: string
  direction: MessageDirection
  channel: MessageChannel
  kind: MessageKind
  text_hi: string | null
  text_en: string | null
  audio_url: string | null
  media_url: string | null
  card: MessageCard | null
  created_at: string
  meta: MessageMeta
}

// Cases
export type CaseKind = 'PERSONAL_CLAIM_REVIEW' | 'DISPUTE' | 'AREA_REVIEW'
export type CaseStatus = 'OPEN' | 'APPROVED' | 'DECLINED' | 'CLOSED'

export interface SlipEvidence {
  media_url: string
  patient_name: string | null
  admission_date: string | null
  discharge_date: string | null
  hospital_name: string | null
  document_type: string | null
  confidence: number
  source: string
}

export interface HourlyEvidence {
  hour: string
  expected_paise: number
  actual_paise: number
}

export interface Precedent {
  subject_id: string
  kind: string
  at: string
  text: string
}

export interface CaseEvidence {
  expected_vs_actual?: HourlyEvidence[]
  slip?: SlipEvidence
  kyc_name?: string
  name_score?: number
  silent_days?: string[]
  merchant_text?: string
  precedents?: Precedent[]
}

export interface Case {
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

// Audit
export interface AuditEntry {
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

export interface AuditVerify {
  valid: boolean
  entries: number
  head_hash: string
  first_bad_seq: number | null
}

// Policy
export interface PolicyAuthority {
  case: string
  alone: string
  human: string
}

export interface PolicyCheck {
  code: string
  severity: 'HARD' | 'SOFT'
  applies: 'area' | 'personal' | 'all'
  passes_when: string
}

export interface PolicyView {
  rules: Record<string, unknown>
  authority: PolicyAuthority[]
  checks: PolicyCheck[]
}

// Backtest
export interface BacktestTrigger {
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

export interface BacktestZone {
  zone_id: string
  premium_per_day_label: string
  premiums_paise: number
  payouts_paise: number
  loss_ratio: number
  chhatri_fp: number
  chhatri_fn: number
}

export interface BacktestPersonal {
  claims: number
  auto_paid: number
  referred: number
  referred_share: number
}

export interface BacktestReport {
  label: string
  seasons: string[]
  generated_at: string
  triggers: BacktestTrigger[]
  zones: BacktestZone[]
  personal: BacktestPersonal
  notes: string[]
}

// SSE event types
export interface SseEventBase<T> {
  id: string
  type: string
  at: string
  data: T
}

export type SseScenarioEvent = SseEventBase<{ clock: ClockState }>
export type SseTickEvent = SseEventBase<{ clock: ClockState }>
export type SseZoneEvent = SseEventBase<{ zone: ZoneSnapshot }>
export type SseHexesEvent = SseEventBase<{ hexes: Record<string, number | null> }>
export type SseAlertEvent = SseEventBase<{ alert: Alert }>
export type SseTriggerEvent = SseEventBase<{ trigger: AreaTrigger }>
export type SseDecisionEvent = SseEventBase<{ decision: Decision }>
export type SsePayoutEvent = SseEventBase<{ payout: Payout }>
export type SseInstalmentEvent = SseEventBase<{ pause: InstalmentPause }>
export type SseMessageEvent = SseEventBase<{ message: Message }>
export type SseSoundboxEvent = SseEventBase<{
  merchant_id: string
  text: string
  amount_label: string
  audio_url: string | null
}>
export type SseCaseEvent = SseEventBase<{ case: Case }>
export type SseAuditEvent = SseEventBase<{
  seq: number
  action: string
  actor: string
  subject_type: string
  subject_id: string
}>
export type SseKpisEvent = SseEventBase<{ kpis: Kpis }>

export type SseEvent =
  | SseScenarioEvent
  | SseTickEvent
  | SseZoneEvent
  | SseHexesEvent
  | SseAlertEvent
  | SseTriggerEvent
  | SseDecisionEvent
  | SsePayoutEvent
  | SseInstalmentEvent
  | SseMessageEvent
  | SseSoundboxEvent
  | SseCaseEvent
  | SseAuditEvent
  | SseKpisEvent

// Session (demo mode only)
export interface SessionData {
  officer_token: string
}

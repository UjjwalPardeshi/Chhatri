/**
 * Static mock fixtures: demo merchants (SPEC §5.4), integration statuses (all SIMULATED — the mock
 * never claims anything is live, SPEC §0.1), the policy view (SPEC §9.1, §9.2, §9.4) and a
 * backtest report in the §19.2 shape (labelled as simulated).
 */
import type { BacktestReport, IntegrationStatus, MerchantSummary, PolicyView } from '../api/types'

export type MockMerchant = MerchantSummary & {
  owner_name_hi: string
  owner_first_en: string
  kyc_name: string
  kyc_name_masked: string
  phone_masked: string
  language: string
  expected_day_paise: number
  instalment_paise: number | null
  premium_per_day_paise: number
}

export const ANIL: MockMerchant = Object.freeze({
  id: 'S-0142',
  shop_name: "Anil's Tea Stall",
  owner_name: 'Anil Jadhav',
  owner_first_en: 'Anil',
  zone_id: 'Z7',
  shop_type: 'TEA_STALL',
  lat: 19.0046,
  lng: 72.8424,
  is_demo: true,
  covered: true,
  owner_name_hi: 'अनिल',
  kyc_name: 'ANIL RAMESH JADHAV',
  kyc_name_masked: 'ANIL R***** JADHAV',
  phone_masked: '+91•••••00142',
  language: 'hi',
  expected_day_paise: 438_000,
  instalment_paise: 60_000,
  premium_per_day_paise: 300,
})

export const RAMESH: MockMerchant = Object.freeze({
  id: 'S-0907',
  shop_name: 'Ramesh Vada Pav',
  owner_name: 'Ramesh Pawar',
  owner_first_en: 'Ramesh',
  zone_id: 'Z3',
  shop_type: 'STREET_FOOD',
  lat: 19.0107,
  lng: 72.8185,
  is_demo: true,
  covered: false,
  owner_name_hi: 'रमेश',
  kyc_name: 'RAMESH PAWAR',
  kyc_name_masked: 'RAMESH P****',
  phone_masked: '+91•••••00907',
  language: 'hi',
  expected_day_paise: 612_000,
  instalment_paise: null,
  premium_per_day_paise: 300,
})

export const MERCHANTS: Readonly<Record<string, MockMerchant>> = Object.freeze({ [ANIL.id]: ANIL, [RAMESH.id]: RAMESH })

export const LENDER_NAME = 'Simulated lender (NBFC partner)'
export const PAYOUT_RAIL = 'Paytm settlement (simulated)'
export const RULES_VERSION = 'pilot-0.1'
export const MOCK_OFFICER_TOKEN = 'mock-officer-token'
export const MOCK_OFFICER_ID = 'demo'

const MOCK_DETAIL = 'mock console backend'

export const INTEGRATIONS: readonly IntegrationStatus[] = Object.freeze([
  { name: 'sarvam_stt', mode: 'SIMULATED', detail: `Saaras speech-to-text: deterministic simulator (${MOCK_DETAIL})` },
  { name: 'sarvam_tts', mode: 'SIMULATED', detail: `Bulbul voice: browser speech (hi-IN) stands in (${MOCK_DETAIL})` },
  { name: 'sarvam_chat', mode: 'SIMULATED', detail: `Rule-based intents only (${MOCK_DETAIL})` },
  { name: 'sarvam_vision', mode: 'SIMULATED', detail: `Slip reader reads the sample slips' embedded data (${MOCK_DETAIL})` },
  { name: 'whatsapp', mode: 'SIMULATED', detail: 'In-console phone simulator' },
  { name: 'paytm', mode: 'SIMULATED', detail: 'Simulated payment link (no Paytm MCP / keys)' },
  { name: 'n8n', mode: 'SIMULATED', detail: 'In-process workflow runner (same steps)' },
  { name: 'memory', mode: 'SIMULATED', detail: 'In-process precedent graph' },
  { name: 'weather', mode: 'SIMULATED', detail: 'Cached real Open-Meteo rainfall drives the replay' },
  { name: 'soundbox', mode: 'SIMULATED', detail: 'Always simulated: in-console Soundbox strip' },
  { name: 'sales_data', mode: 'SIMULATED', detail: 'Always simulated: synthetic hourly sales' },
  { name: 'alerts', mode: 'SIMULATED', detail: 'Always simulated: scripted IMD-style alerts' },
  { name: 'payout_rail', mode: 'SIMULATED', detail: 'Always simulated: settlement rail, 4 min' },
  { name: 'lender', mode: 'SIMULATED', detail: 'Always simulated: NBFC partner instalment pause' },
  { name: 'kyc', mode: 'SIMULATED', detail: 'Always simulated: KYC names from the demo city' },
])

export const POLICY: PolicyView = Object.freeze({
  rules: {
    version: RULES_VERSION,
    payout_share: 0.5,
    area: { index_floor_pct: 50, consecutive_hours: 3, min_shops_in_index: 20, daily_cap_rupees: 2500 },
    personal: { daily_cap_rupees: 1500, max_auto_days: 3, name_match_min_score: 85, slip_confidence_min: 0.8 },
    cover: { waiting_period_days: 7, alert_lookahead_hours: 72 },
    annual_limit_rupees: 30000,
    dispute_sla_hours: 24,
    payout_rail_delay_minutes: 4,
    instalment_pause_delay_minutes: 5,
    premium: { loading: 0.35, min_per_day_rupees: 2, first_payment_days: 30 },
  },
  authority: [
    { case: 'Area drop during an alert, index clear', alone: 'Pays', human: 'Only if the merchant disputes' },
    { case: 'Personal claim, slip matches name and dates', alone: 'Pays up to the daily cap', human: 'Anything above the cap' },
    { case: "Slip unclear or dates don't match", alone: 'Never', human: 'Always' },
    { case: 'Cover bought after an alert', alone: 'Never', human: 'Waiting period applies' },
  ],
  checks: [
    { code: 'COVER_IN_FORCE', severity: 'HARD', applies: 'all', passes_when: 'cover exists, starts on or before the event date, status ACTIVE' },
    { code: 'PREMIUM_PREPAID', severity: 'HARD', applies: 'all', passes_when: 'prepaid through the event date (Insurance Act s.64VB)' },
    { code: 'COVER_BEFORE_ALERT', severity: 'HARD', applies: 'area', passes_when: 'cover bought before the alert was issued' },
    { code: 'ALERT_ACTIVE', severity: 'HARD', applies: 'area', passes_when: 'alert valid over the whole trigger window' },
    { code: 'INDEX_QUORUM', severity: 'HARD', applies: 'area', passes_when: 'at least 20 shops in the zone index' },
    { code: 'BELOW_FLOOR', severity: 'HARD', applies: 'area', passes_when: 'all 3 hourly indices below 50%' },
    { code: 'BELOW_MODEL_RANGE', severity: 'HARD', applies: 'area', passes_when: "window index below the zone's lower bound" },
    { code: 'SILENCE_VERIFIED', severity: 'HARD', applies: 'personal', passes_when: 'every claimed day is a verified silent day' },
    { code: 'SLIP_READABLE', severity: 'SOFT', applies: 'personal', passes_when: 'medical slip present, confidence ≥ 0.80' },
    { code: 'NAME_MATCHES_KYC', severity: 'SOFT', applies: 'personal', passes_when: 'name score ≥ 85' },
    { code: 'DATES_MATCH', severity: 'SOFT', applies: 'personal', passes_when: 'admission ≤ each silent day ≤ discharge' },
    { code: 'WITHIN_AUTO_LIMIT', severity: 'SOFT', applies: 'personal', passes_when: 'silent days ≤ 3' },
    { code: 'NOT_ALREADY_PAID', severity: 'HARD', applies: 'all', passes_when: 'no approved payout for this merchant, date and kind' },
    { code: 'WITHIN_ANNUAL_LIMIT', severity: 'HARD', applies: 'all', passes_when: 'paid in the rolling year + amount ≤ ₹30,000' },
  ],
}) as PolicyView

export const BACKTEST: BacktestReport = Object.freeze({
  label: 'simulated sales · real Open-Meteo rainfall',
  seasons: ['Jun–Sep 2024', 'Jun–Sep 2025'],
  generated_at: '2025-09-30T09:00:00+05:30',
  triggers: [
    {
      name: 'chhatri',
      real_drops: 64,
      real_drops_paid: 58,
      recall: 0.906,
      payouts: 61,
      payouts_no_real_drop: 3,
      false_positive_rate: 0.049,
      paid_paise: 1_842_760_00,
      trigger_to_money: 'same day · 4 min',
      documents_per_area_claim: 0,
    },
    {
      name: 'weather_only',
      real_drops: 64,
      real_drops_paid: 35,
      recall: 0.547,
      payouts: 79,
      payouts_no_real_drop: 44,
      false_positive_rate: 0.557,
      paid_paise: 2_310_450_00,
      trigger_to_money: 'same day · 4 min',
      documents_per_area_claim: 0,
    },
  ],
  zones: [
    { zone_id: 'Z3', premium_per_day_label: '₹3', premiums_paise: 30_883_00, payouts_paise: 19_142_00, loss_ratio: 0.62, chhatri_fp: 1, chhatri_fn: 1 },
    { zone_id: 'Z7', premium_per_day_label: '₹3', premiums_paise: 10_074_00, payouts_paise: 6_890_00, loss_ratio: 0.68, chhatri_fp: 0, chhatri_fn: 1 },
    { zone_id: 'Z9', premium_per_day_label: '₹2', premiums_paise: 9_344_00, payouts_paise: 3_118_00, loss_ratio: 0.33, chhatri_fp: 0, chhatri_fn: 0 },
    { zone_id: 'Z12', premium_per_day_label: '₹3', premiums_paise: 27_375_00, payouts_paise: 17_240_00, loss_ratio: 0.63, chhatri_fp: 1, chhatri_fn: 2 },
  ],
  personal: { claims: 42, auto_paid: 31, referred: 11, referred_share: 0.262 },
  notes: [
    'Mock console data: numbers illustrate the report layout; the live backend serves backend/artifacts/backtest/report.json.',
    'Real drop = zone-day whose true shock-caused loss is at least 40% of expected day sales.',
    'Weather-only trigger: reference grid point daily rain ≥ 64.5 mm (IMD "heavy").',
  ],
}) as BacktestReport

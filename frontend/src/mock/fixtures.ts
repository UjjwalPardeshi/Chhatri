/**
 * Static mock fixtures: demo merchants (SPEC §5.4), integration statuses (all SIMULATED — the mock
 * never claims anything is live, SPEC §0.1), the policy view (SPEC §9.1, §9.2, §9.4) and a
 * backtest report in the §19.2 shape (labelled as simulated).
 */
import type { BacktestReport, IntegrationStatus, MerchantSummary, PolicyView } from '../api/types'
import backtestReport from './data/backtest.json'
import zonePrices from './data/premiums.json'

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

/** The SPEC §9.1 minimum a day (₹2) for a zone that premiums.json does not price, like the backend. */
const MIN_PREMIUM_PER_DAY_PAISE = 200

/**
 * The daily premium of a zone in paise: a copy of `backend/artifacts/premiums.json` (Z7 ₹18.62, Z3 ₹14.16), so a mock
 * quote reads what the product quotes (DEMO.md: Ramesh pays ₹424.80 for 30 days), not a flat ₹3 a day.
 */
export function zonePremiumPaise(zoneId: string): number {
  return (zonePrices as Readonly<Record<string, number>>)[zoneId] ?? MIN_PREMIUM_PER_DAY_PAISE
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
  premium_per_day_paise: zonePremiumPaise('Z7'),
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
  premium_per_day_paise: zonePremiumPaise('Z3'),
})

export const MERCHANTS: Readonly<Record<string, MockMerchant>> = Object.freeze({ [ANIL.id]: ANIL, [RAMESH.id]: RAMESH })

export const LENDER_NAME = 'Simulated lender (NBFC partner)'
export const PAYOUT_RAIL = 'Paytm settlement (simulated)'
export const RULES_VERSION = 'pilot-0.1'
export const MOCK_OFFICER_TOKEN = 'mock-officer-token'
export const MOCK_OFFICER_ID = 'officer'

const MOCK_DETAIL = 'mock console backend'

const BASE_INTEGRATIONS: readonly IntegrationStatus[] = Object.freeze([
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
  { name: 'gemini_chat', mode: 'SIMULATED', detail: `Gemini chat: no key in the static demo (${MOCK_DETAIL})` },
  { name: 'gemini_vision', mode: 'SIMULATED', detail: `Gemini slip reader: no key in the static demo (${MOCK_DETAIL})` },
])

/** Components with a fallback path (fs-08 9.2); the mock can force only the lender, which is already simulated. */
export const MOCK_FORCEABLE: ReadonlySet<string> = new Set(['lender'])
const MOCK_PROVIDER: Readonly<Record<string, string>> = { sarvam_chat: 'mock', gemini_chat: 'mock', sarvam_tts: 'browser' }
const MOCK_REASON: Readonly<Record<string, string>> = { sarvam_chat: 'MOCK_BACKEND', sarvam_vision: 'MOCK_BACKEND', sarvam_stt: 'MOCK_BACKEND', gemini_chat: 'MOCK_BACKEND', gemini_vision: 'MOCK_BACKEND' }

/** The rows the mock serves: every component SIMULATED, the lender FORCED to FALLBACK while its switch is on (fs-08 9.7). */
export function integrationRows(lenderForced: boolean): IntegrationStatus[] {
  return BASE_INTEGRATIONS.map((row) => {
    const forced = row.name === 'lender' && lenderForced
    const base = { ...row, provider: MOCK_PROVIDER[row.name] ?? 'simulated', model: null, fallback_reason: MOCK_REASON[row.name] ?? null, switchable: MOCK_FORCEABLE.has(row.name), forced, last_call: null }
    return forced ? { ...base, mode: 'FALLBACK' as const, detail: 'Simulated lender (NBFC partner), not answering: forced for the demo', provider: 'simulated', fallback_reason: 'FORCED' } : base
  })
}

export const INTEGRATIONS: readonly IntegrationStatus[] = Object.freeze(integrationRows(false))

/** The pilot rules (`rules.yaml`, SPEC §9.1) with their real shape, so the mock reads its numbers from one place. */
export const POLICY_RULES = Object.freeze({
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
})

export const POLICY: PolicyView = Object.freeze({
  rules: POLICY_RULES,
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

/**
 * The backtest the mock serves: a copy of GET /api/backtest from the committed artefact
 * (backend/artifacts/backtest/report.json, B6), so mock mode shows the same numbers as the real
 * backend. Refresh it after `make data` with: curl -s $API/api/backtest | jq .data > src/mock/data/backtest.json
 */
export const BACKTEST: BacktestReport = Object.freeze(backtestReport as BacktestReport)

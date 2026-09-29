/**
 * Mock fixtures for development
 * Golden numbers from SPEC §17.2, §17.4
 */

import type {
  ClockState,
  ZoneSnapshot,
  Kpis,
  AreaTrigger,
  Alert,
  MerchantDetail,
  Case,
  Decision,
  Message,
  FeedItem,
  PolicyView,
  BacktestReport,
  Payout,
  StateSnapshot,
} from '../types'

// Time utilities for IST
export function isoNow(): string {
  return new Date().toISOString().replace('Z', '+05:30')
}

export function isoDate(date: Date): string {
  const iso = date.toISOString()
  return iso.replace('Z', '+05:30')
}

// Clock state (monsoon scenario)
export const mockClockState: ClockState = {
  now: '2025-08-19T17:00:00+05:30',
  scenario: 'monsoon',
  scenario_title: 'monsoon replay',
  running: false,
  speed: 6,
  start: '2025-08-19T08:00:00+05:30',
  end: '2025-08-19T20:00:00+05:30',
  label: 'Mumbai · monsoon replay · 17:00 · simulated',
}

// Zones (golden numbers from SPEC §17.2)
const zoneZ7: ZoneSnapshot = {
  zone_id: 'Z7',
  ward: 'F/S',
  name: 'Parel · Lalbaug',
  shops: 46,
  index_pct: 37,
  live_index_pct: 37,
  lower_bound_pct: 40,
  status: 'triggered',
  hours_below: 3,
  alert: {
    id: 'A-20250818-01',
    level: 'RED',
    kind: 'RAIN',
    valid_from: '2025-08-19T14:00:00+05:30',
    valid_to: '2025-08-19T20:00:00+05:30',
    headline_en: 'Red alert from 14:00',
  },
  label: 'Z7 · 37% · 46 shops',
}

const zoneZ3: ZoneSnapshot = {
  zone_id: 'Z3',
  ward: 'G/S',
  name: 'Worli · Lower Parel',
  shops: 141,
  index_pct: 38,
  live_index_pct: 38,
  lower_bound_pct: 40,
  status: 'triggered',
  hours_below: 3,
  alert: {
    id: 'A-20250818-01',
    level: 'RED',
    kind: 'RAIN',
    valid_from: '2025-08-19T14:00:00+05:30',
    valid_to: '2025-08-19T20:00:00+05:30',
    headline_en: 'Red alert from 14:00',
  },
  label: 'Z3 · 38% · 141 shops',
}

const zoneZ12: ZoneSnapshot = {
  zone_id: 'Z12',
  ward: 'E',
  name: 'Byculla',
  shops: 125,
  index_pct: 47,
  live_index_pct: 47,
  lower_bound_pct: 45,
  status: 'triggered',
  hours_below: 3,
  alert: {
    id: 'A-20250818-01',
    level: 'RED',
    kind: 'RAIN',
    valid_from: '2025-08-19T14:00:00+05:30',
    valid_to: '2025-08-19T20:00:00+05:30',
    headline_en: 'Red alert from 14:00',
  },
  label: 'Z12 · 47% · 125 shops',
}

const zoneZ9: ZoneSnapshot = {
  zone_id: 'Z9',
  ward: 'M/W',
  name: 'Chembur',
  shops: 64,
  index_pct: 61,
  live_index_pct: 61,
  lower_bound_pct: 40,
  status: 'slow_day',
  hours_below: 0,
  alert: null,
  label: 'Z9 · 61% · 64 shops',
}

export const mockZones: Record<string, ZoneSnapshot> = {
  'Z7': zoneZ7,
  'Z3': zoneZ3,
  'Z12': zoneZ12,
  'Z9': zoneZ9,
}

// KPIs (golden numbers)
export const mockKpis: Kpis = {
  zones_triggered: 3,
  shops_paid: 312,
  trigger_to_money_min: 4,
  total_paid_paise: 5890000, // ₹58,900
  total_paid_label: '₹58,900',
  instalments_paused: 1,
}

// Anil's Tea Stall (demo merchant S-0142)
export const mockAnil: MerchantDetail = {
  id: 'S-0142',
  shop_name: 'Anil\'s Tea Stall',
  owner_name: 'Anil Jadhav',
  owner_name_hi: 'अनिल',
  kyc_name_masked: 'ANIL RAMESH J***',
  phone_masked: '+91••••••12345',
  zone_id: 'Z7',
  shop_type: 'TEA_STALL',
  lat: 19.0046,
  lng: 72.8424,
  is_demo: true,
  covered: true,
  language: 'hi',
  cover: {
    status: 'ACTIVE',
    starts_on: '2025-05-20',
    prepaid_through: '2025-08-25',
    premium_per_day_label: '₹5',
  },
  loan: {
    daily_instalment_label: '₹600',
    lender_name: 'Simulated lender (NBFC partner)',
  },
  expected_today_label: '₹4,380',
  payouts: [],
  decisions: [],
}

// Alert (Red rain alert)
export const mockAlert: Alert = {
  id: 'A-20250818-01',
  kind: 'RAIN',
  level: 'RED',
  zone_ids: ['Z3', 'Z7', 'Z12'],
  issued_at: '2025-08-18T17:30:00+05:30',
  valid_from: '2025-08-19T14:00:00+05:30',
  valid_to: '2025-08-19T20:00:00+05:30',
  source: 'IMD-style nowcast · simulated',
  headline_en: 'Red alert from 14:00',
  headline_hi: 'लाल अलर्ट 14:00 से',
}

// Area triggers (golden numbers)
const triggerZ7: AreaTrigger = {
  id: 'E-Z7-20250819',
  zone_id: 'Z7',
  alert_id: 'A-20250818-01',
  window_start: '2025-08-19T14:00:00+05:30',
  window_end: '2025-08-19T17:00:00+05:30',
  index_pct: 37,
  drop_pct: 63,
  hourly_index_pct: [37, 37, 37],
  lower_bound_pct: 40,
  shops_in_index: 46,
  fired_at: '2025-08-19T17:00:00+05:30',
}

const triggerZ3: AreaTrigger = {
  id: 'E-Z3-20250819',
  zone_id: 'Z3',
  alert_id: 'A-20250818-01',
  window_start: '2025-08-19T14:00:00+05:30',
  window_end: '2025-08-19T17:00:00+05:30',
  index_pct: 38,
  drop_pct: 62,
  hourly_index_pct: [38, 38, 38],
  lower_bound_pct: 40,
  shops_in_index: 141,
  fired_at: '2025-08-19T17:00:00+05:30',
}

const triggerZ12: AreaTrigger = {
  id: 'E-Z12-20250819',
  zone_id: 'Z12',
  alert_id: 'A-20250818-01',
  window_start: '2025-08-19T14:00:00+05:30',
  window_end: '2025-08-19T17:00:00+05:30',
  index_pct: 47,
  drop_pct: 53,
  hourly_index_pct: [47, 47, 47],
  lower_bound_pct: 45,
  shops_in_index: 125,
  fired_at: '2025-08-19T17:00:00+05:30',
}

export const mockTriggers: AreaTrigger[] = [triggerZ7, triggerZ3, triggerZ12]

// Decision (Anil's payout)
export const mockDecision: Decision = {
  id: 'D-000001',
  claim_id: 'CL-000001',
  merchant_id: 'S-0142',
  outcome: 'APPROVED',
  amount_paise: 138000, // ₹1,380
  amount_label: '₹1,380',
  checks: [
    {
      code: 'COVER_IN_FORCE',
      status: 'PASS',
      severity: 'HARD',
      label_en: 'Cover in force',
      detail_en: 'Active cover found',
      observed: 'ACTIVE',
      required: 'ACTIVE',
    },
    {
      code: 'PREMIUM_PREPAID',
      status: 'PASS',
      severity: 'HARD',
      label_en: 'Premium prepaid',
      detail_en: 'Premium paid through 2025-08-25',
      observed: '2025-08-25',
      required: '2025-08-19',
    },
  ],
  rules_version: 'pilot-0.1',
  decided_at: '2025-08-19T17:00:00+05:30',
  decided_by: 'policy-engine',
  explanation: {
    weekday_en: 'Tuesday',
    weekday_hi: 'मंगलवार',
    expected_day_paise: 438000,
    expected_day_label: '₹4,380',
    drop_pct: 63,
    share_pct: 50,
    days: 1,
    cap_paise: 250000,
    capped: false,
    amount_paise: 138000,
    amount_label: '₹1,380',
    formula_en: '½ × ₹4,380 × 63% = ₹1,380',
    formula_hi: '₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380',
  },
  referral_reason: null,
  supersedes: null,
}

// Payout (Anil's credit)
export const mockPayout: Payout = {
  id: 'P-000001',
  decision_id: 'D-000001',
  merchant_id: 'S-0142',
  amount_paise: 138000,
  amount_label: '₹1,380',
  status: 'CREDITED',
  rail: 'Paytm settlement (simulated)',
  created_at: '2025-08-19T17:00:00+05:30',
  credited_at: '2025-08-19T17:04:00+05:30',
  reference: 'SIM-20250819-000001',
}

// Case (Sunil Pawar - REFERRED)
export const mockCase: Case = {
  id: 'C-2291',
  kind: 'PERSONAL_CLAIM_REVIEW',
  merchant_id: 'S-0142',
  merchant_name: 'Sunil Pawar',
  status: 'OPEN',
  opened_at: '2025-08-21T11:30:00+05:30',
  due_by: '2025-08-22T11:30:00+05:30',
  summary_en: 'Personal claim: hospital slip submitted',
  decision: {
    id: 'D-000002',
    claim_id: 'CL-000002',
    merchant_id: 'S-0142',
    outcome: 'REFERRED',
    amount_paise: 150000,
    amount_label: '₹1,500',
    checks: [
      {
        code: 'NAME_MATCHES_KYC',
        status: 'UNSURE',
        severity: 'SOFT',
        label_en: 'Name matches KYC',
        detail_en: 'Patient name on slip does not match KYC',
        observed: 'Sunil Pawar',
        required: 'Anil Ramesh Jadhav',
      },
    ],
    rules_version: 'pilot-0.1',
    decided_at: '2025-08-21T11:30:00+05:30',
    decided_by: 'policy-engine',
    explanation: null,
    referral_reason: 'NAME_MATCHES_KYC UNSURE',
    supersedes: null,
  },
  evidence: {
    slip: {
      media_url: '/api/media/MD-000001',
      patient_name: 'Sunil Pawar',
      admission_date: '2025-08-20',
      discharge_date: null,
      hospital_name: 'KEM Hospital',
      document_type: 'admission_slip',
      confidence: 0.92,
      source: 'Sarvam doc-ai · simulated',
    },
    kyc_name: 'ANIL RAMESH JADHAV',
    name_score: 60,
  },
  resolution: null,
  resolved_by: null,
  resolved_at: null,
}

// Messages (WhatsApp conversation)
export const mockMessages: Message[] = [
  {
    id: 'M-000001',
    merchant_id: 'S-0142',
    direction: 'OUTBOUND',
    channel: 'WHATSAPP',
    kind: 'TEXT',
    text_hi: 'अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।',
    text_en: 'Anil ji, heavy rain cut your area\'s sales by 63% today.',
    audio_url: null,
    media_url: null,
    card: null,
    created_at: '2025-08-19T17:04:00+05:30',
    meta: {},
  },
  {
    id: 'M-000002',
    merchant_id: 'S-0142',
    direction: 'OUTBOUND',
    channel: 'WHATSAPP',
    kind: 'PAYOUT_CARD',
    text_hi: null,
    text_en: null,
    audio_url: null,
    media_url: null,
    card: {
      amount_label: '₹1,380',
      subtitle_hi: 'आज के सेटलमेंट के साथ जमा',
      subtitle_en: 'Credited with today\'s settlement',
      badge: 'No claim needed',
    },
    created_at: '2025-08-19T17:04:00+05:30',
    meta: {},
  },
]

// Feed
export const mockFeed: FeedItem[] = [
  {
    id: 1,
    at: '2025-08-19T14:00:00+05:30',
    type: 'alert',
    text_en: 'RED alert issued for Z7, Z3, Z12',
    zone_id: 'Z7',
  },
  {
    id: 2,
    at: '2025-08-19T17:00:00+05:30',
    type: 'trigger',
    text_en: '3 zones triggered',
  },
  {
    id: 3,
    at: '2025-08-19T17:04:00+05:30',
    type: 'payout',
    text_en: '312 shops paid ₹58,900',
  },
]

// Policy
export const mockPolicy: PolicyView = {
  rules: {
    version: 'pilot-0.1',
    payout_share: 0.5,
    area: {
      index_floor_pct: 50,
      consecutive_hours: 3,
      min_shops_in_index: 20,
      daily_cap_rupees: 2500,
    },
    personal: {
      daily_cap_rupees: 1500,
      max_auto_days: 3,
    },
  },
  authority: [
    {
      case: 'Area drop during an alert, index clear',
      alone: 'Pays',
      human: 'Only if the merchant disputes',
    },
    {
      case: 'Personal claim, slip matches name and dates',
      alone: 'Pays up to the daily cap',
      human: 'Anything above the cap',
    },
  ],
  checks: [
    {
      code: 'COVER_IN_FORCE',
      severity: 'HARD',
      applies: 'all',
      passes_when: 'Active cover exists',
    },
  ],
}

// Backtest
export const mockBacktest: BacktestReport = {
  label: 'Backtest on simulated sales · real Open-Meteo rainfall',
  seasons: ['2024-06-01 to 2024-09-30', '2025-06-01 to 2025-09-30'],
  generated_at: '2025-08-19T17:00:00+05:30',
  triggers: [
    {
      name: 'chhatri',
      real_drops: 45,
      real_drops_paid: 42,
      recall: 0.933,
      payouts: 48,
      payouts_no_real_drop: 3,
      false_positive_rate: 0.062,
      paid_paise: 580000000,
      trigger_to_money: 'same day',
      documents_per_area_claim: 0,
    },
  ],
  zones: [
    {
      zone_id: 'Z7',
      premium_per_day_label: '₹8',
      premiums_paise: 2920000,
      payouts_paise: 8000000,
      loss_ratio: 2.74,
      chhatri_fp: 2,
      chhatri_fn: 1,
    },
  ],
  personal: {
    claims: 12,
    auto_paid: 10,
    referred: 2,
    referred_share: 0.167,
  },
  notes: ['Monsoon season shows strong trigger performance'],
}

// State snapshot
export function createStateSnapshot(): StateSnapshot {
  return {
    clock: mockClockState,
    zones: Object.values(mockZones),
    hexes: {}, // Populated by the mock server
    kpis: mockKpis,
    triggers: mockTriggers,
    explanations: {
      'Z9':
        'Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That\'s a slow day, not a loss event, so Chhatri doesn\'t pay.',
    },
    feed: mockFeed,
    demo_merchant_id: 'S-0142',
    rain_band: null,
  }
}

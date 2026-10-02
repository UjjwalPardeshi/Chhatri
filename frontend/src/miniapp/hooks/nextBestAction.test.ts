/** The next-best-action rules of fs-04 section 12: one case per rule id, one per priority conflict, and no offer (AC-37). */
import { describe, expect, it } from 'vitest'

import type { ClaimItem, ClaimStep, Cover, CoverStatus } from '../../api/types'
import { en } from '../copy/en'
import { hi } from '../copy/hi'
import {
  NBA_KINDS,
  nextBestAction,
  type NbaBuyState,
  type NbaInput,
  type NbaKind,
  type NbaResult,
  type NbaRuleId,
} from './nextBestAction'
import { SCREENS, type Screen } from './useMiniappUrl'

function cover(status: CoverStatus, over: Partial<Cover> = {}): Cover {
  const has = status !== 'NONE'
  return {
    merchant_id: 'S-0142',
    cover_id: has ? 'CV-0142' : null,
    status,
    status_text_hi: 'x',
    status_text_en: 'x',
    zone_id: 'Z7',
    zone_name: 'Parel',
    purchased_at: null,
    starts_on: status === 'WAITING' ? '2025-08-25' : has ? '2025-03-17' : null,
    prepaid_through: has ? '2025-08-22' : null,
    waiting_period_days: 7,
    premium_per_day_paise: 1862,
    premium_per_day_label: '₹18.62',
    premium_due: false,
    annual_limit_paise: has ? 3_000_000 : null,
    annual_limit_label: has ? '₹30,000' : null,
    amount_claimed_paise: has ? 138_000 : null,
    amount_claimed_label: has ? '₹1,380' : null,
    amount_remaining_paise: has ? 2_862_000 : null,
    amount_remaining_label: has ? '₹28,620' : null,
    alert_active: false,
    alert_id: null,
    ...over,
  }
}

const NAMES = ['Detected', 'Checked', 'Decided', 'Paid', 'EDI holiday'] as const
function steps(...statuses: ClaimStep['status'][]): ClaimStep[] {
  return NAMES.map((name, i) => ({ name, status: statuses[i] ?? 'pending', result: null, at: null, reason_hi: null, reason_en: null, reason_code: null }))
}

function claim(kind: ClaimItem['kind'], over: Partial<ClaimItem> = {}): ClaimItem {
  return {
    claim_id: kind === 'DISPUTE' ? null : 'CL-000001',
    disputed_claim_id: kind === 'DISPUTE' ? 'CL-000001' : null,
    kind,
    claim_at: '2025-08-19T17:00:00+05:30',
    zone_id: 'Z7',
    trigger_id: null,
    decision_id: 'D-000142',
    outcome: 'APPROVED',
    amount_paise: 138_000,
    amount_label: '₹1,380',
    steps: steps('completed', 'completed', 'completed', 'completed', 'skipped'),
    case_id: null,
    case_status: null,
    due_by: null,
    resolution: null,
    ...over,
  }
}

const paid = claim('AREA')
const referred = claim('PERSONAL', { claim_id: 'CL-000002', decision_id: 'D-000150', outcome: 'REFERRED', amount_paise: null, amount_label: null, case_id: 'C-2291', case_status: 'OPEN', steps: steps('completed', 'completed', 'current') })
const disputeOpen = claim('DISPUTE', { case_id: 'C-2292', case_status: 'OPEN', claim_id: null, disputed_claim_id: 'CL-000001' })
const declined = claim('PERSONAL', { claim_id: 'CL-000003', outcome: 'DECLINED', amount_paise: null, amount_label: null, steps: steps('completed', 'completed', 'completed', 'skipped', 'skipped') })
const waitingForSlip = claim('PERSONAL', { claim_id: 'CL-000005', decision_id: null, outcome: null, amount_paise: null, amount_label: null, steps: steps('current') })
const approvedNotCredited = claim('AREA', { claim_id: 'CL-000004', steps: steps('completed', 'completed', 'completed', 'current') })

const base = { lang: 'en', cover: cover('ACTIVE'), claims: [], slaHours: 24 } as const
const input = (over: Partial<NbaInput> & Pick<NbaInput, 'screen'>): NbaInput => ({ ...base, ...over })
const run = (over: Partial<NbaInput> & Pick<NbaInput, 'screen'>): NbaResult => nextBestAction(input(over))
const quoted: NbaBuyState = { phase: 'quoted', simulated: true }

type Case = { name: string; input: Partial<NbaInput> & Pick<NbaInput, 'screen'>; id: NbaRuleId; kind: NbaKind }

const RULE_CASES: Case[] = [
  // Screen rules
  { name: 'S2 with no cover', input: { screen: 'coverage', cover: cover('NONE') }, id: 'get_cover_from_coverage', kind: 'BUY_COVER' },
  { name: 'S2 with a claim', input: { screen: 'coverage', claims: [paid] }, id: 'see_claims', kind: 'VIEW' },
  { name: 'S2 otherwise', input: { screen: 'coverage' }, id: 'home_from_coverage', kind: 'VIEW' },
  { name: 'S3 with no quote yet', input: { screen: 'buy', cover: cover('NONE'), buy: { phase: 'idle', simulated: true } }, id: 'check_price', kind: 'FOCUS' },
  { name: 'S3 with a quote and a link', input: { screen: 'buy', cover: cover('NONE'), buy: quoted }, id: 'pay', kind: 'FOCUS' },
  { name: 'S3 once paid', input: { screen: 'buy', cover: cover('WAITING'), buy: { phase: 'paid', simulated: true } }, id: 'home_after_paid', kind: 'VIEW' },
  { name: 'S3 when the merchant already has cover', input: { screen: 'buy', cover: cover('ACTIVE'), buy: { phase: 'idle', simulated: true } }, id: 'home_when_covered', kind: 'VIEW' },
  { name: 'S4 with claims', input: { screen: 'claims', claims: [paid] }, id: 'open_latest', kind: 'VIEW' },
  { name: 'S4 with none', input: { screen: 'claims' }, id: 'see_coverage_empty', kind: 'VIEW' },
  { name: 'S5 with a dispute open', input: { screen: 'claim', claim: paid, claims: [disputeOpen, paid] }, id: 'wait_for_officer', kind: 'WAIT' },
  { name: 'S5 for a referred claim', input: { screen: 'claim', claim: referred, claims: [referred] }, id: 'wait_for_officer', kind: 'WAIT' },
  { name: 'S5 for a paid claim', input: { screen: 'claim', claim: paid, claims: [paid] }, id: 'see_why', kind: 'VIEW' },
  { name: 'S5 otherwise', input: { screen: 'claim', claim: declined, claims: [declined] }, id: 'back_to_claims', kind: 'VIEW' },
  { name: 'S6 always', input: { screen: 'why', claim: paid, claims: [paid] }, id: 'see_receipt', kind: 'VIEW' },
  { name: 'S7 for a paid claim', input: { screen: 'receipt', claim: paid, claims: [paid] }, id: 'disagree', kind: 'FOCUS' },
  { name: 'S9 always', input: { screen: 'settings' }, id: 'home_after_language', kind: 'VIEW' },
  // The global list
  { name: 'global 1: a dispute is open', input: { screen: 'home', claims: [disputeOpen, paid] }, id: 'see_dispute_case', kind: 'WAIT' },
  { name: 'global 2: a personal claim is referred', input: { screen: 'home', claims: [referred] }, id: 'see_referred_claim', kind: 'WAIT' },
  { name: 'global 4: the latest claim is paid', input: { screen: 'home', claims: [paid] }, id: 'see_why', kind: 'VIEW' },
  { name: 'global 5: cover is waiting', input: { screen: 'help', cover: cover('WAITING') }, id: 'see_coverage_waiting', kind: 'VIEW' },
  { name: 'global 6: no cover', input: { screen: 'home', cover: cover('NONE') }, id: 'get_cover', kind: 'BUY_COVER' },
  { name: 'global 7: the premium is due', input: { screen: 'home', cover: cover('ACTIVE', { premium_due: true }) }, id: 'see_premium', kind: 'VIEW' },
  { name: 'global 8: an alert is in force and cover is active', input: { screen: 'home', cover: cover('ACTIVE', { alert_active: true, alert_id: 'A-20250818-01' }) }, id: 'alert_notice', kind: 'VIEW' },
  { name: 'global 10: otherwise', input: { screen: 'home' }, id: 'see_coverage', kind: 'VIEW' },
  // Wave 2 and 3 rules, each behind its flag
  { name: 'S3 with the consent block incomplete', input: { screen: 'buy', cover: cover('NONE'), buy: { phase: 'idle', simulated: true, consent: { firstUnticked: 'buy-consent-SALES_DATA_FOR_CLAIM' } } }, id: 'tick_consent', kind: 'FOCUS' },
  { name: 'global 3: a personal claim waits for the slip', input: { screen: 'home', claims: [waitingForSlip], features: { slip: true } }, id: 'send_slip', kind: 'SEND_SLIP' },
  { name: 'global 9: Ask Chhatri is on', input: { screen: 'home', features: { ask: true } }, id: 'ask', kind: 'ASK' },
]

describe('nextBestAction: one case per rule', () => {
  it.each(RULE_CASES)('$name is $id', ({ input: given, id, kind }) => {
    const result = run(given)
    expect({ id: result.id, kind: result.kind }).toEqual({ id, kind })
    expect(result.sentenceKey).toBe(`nba.${id}`)
    expect(result.buttonKey).toBe(id === 'pay' && quoted.simulated ? 'buy.simulate' : `nba.${id}.btn`)
  })

  it('has a Hindi and an English sentence and button for every rule it can return', () => {
    for (const { input: given } of RULE_CASES) {
      const { sentenceKey, buttonKey } = run(given)
      expect([sentenceKey, typeof en[sentenceKey], typeof hi[sentenceKey]]).toEqual([sentenceKey, 'string', 'string'])
      expect([buttonKey, typeof en[buttonKey], typeof hi[buttonKey]]).toEqual([buttonKey, 'string', 'string'])
    }
  })
})

const winner = (over: Partial<NbaInput> & Pick<NbaInput, 'screen'>) => run(over).id

describe('nextBestAction: priority conflicts', () => {

  it('an open dispute beats a referred claim and a paid one', () => {
    expect(winner({ screen: 'home', claims: [referred, disputeOpen, paid] })).toBe('see_dispute_case')
  })
  it('a referred claim beats a paid latest claim', () => {
    expect(winner({ screen: 'home', claims: [paid, referred] })).toBe('see_referred_claim')
  })
  it('a paid latest claim beats a waiting cover, a due premium and an alert', () => {
    expect(winner({ screen: 'home', claims: [paid], cover: cover('ACTIVE', { premium_due: true, alert_active: true, alert_id: 'A-1' }) })).toBe('see_why')
  })
  it('only the latest claim counts for see_why: an older paid claim under a declined one does not', () => {
    expect(winner({ screen: 'home', claims: [declined, paid] })).toBe('see_coverage')
  })
  it('a claim that is approved but not credited yet is not "paid"', () => {
    expect(winner({ screen: 'home', claims: [approvedNotCredited] })).toBe('see_coverage')
  })
  it('a waiting cover beats no other rule below it, and no cover beats an alert', () => {
    expect(winner({ screen: 'home', cover: cover('WAITING', { alert_active: true, alert_id: 'A-1' }) })).toBe('see_coverage_waiting')
    expect(winner({ screen: 'home', cover: cover('NONE', { alert_active: true, alert_id: 'A-1' }) })).toBe('get_cover')
  })
  it('a due premium beats the alert notice', () => {
    expect(winner({ screen: 'home', cover: cover('ACTIVE', { premium_due: true, alert_active: true, alert_id: 'A-1' }) })).toBe('see_premium')
  })
  it('an alert says nothing while the cover is not active', () => {
    expect(winner({ screen: 'home', cover: cover('LAPSED', { alert_active: true, alert_id: 'A-1' }) })).toBe('see_coverage')
  })
  it('the screen rule is checked first: S2 with a paid claim says see_claims, not see_why', () => {
    expect(winner({ screen: 'coverage', claims: [paid] })).toBe('see_claims')
  })
  it('S2 with no cover says get cover before see claims', () => {
    expect(winner({ screen: 'coverage', cover: cover('NONE'), claims: [paid] })).toBe('get_cover_from_coverage')
  })
  it('S3: paid beats already covered, and already covered beats a quote', () => {
    expect(winner({ screen: 'buy', cover: cover('WAITING'), buy: { phase: 'paid', simulated: true } })).toBe('home_after_paid')
    expect(winner({ screen: 'buy', cover: cover('WAITING'), buy: quoted })).toBe('home_when_covered')
  })
  it('S5: an open dispute beats see_why on a paid claim', () => {
    expect(winner({ screen: 'claim', claim: paid, claims: [disputeOpen, paid] })).toBe('wait_for_officer')
  })
  it('S5: a closed dispute does not hold the claim back', () => {
    const closed = { ...disputeOpen, case_status: 'CLOSED' } as const
    expect(winner({ screen: 'claim', claim: paid, claims: [closed, paid] })).toBe('see_why')
  })
  it('S7 for a claim that is not paid falls back to the global list', () => {
    expect(winner({ screen: 'receipt', claim: referred, claims: [referred] })).toBe('see_referred_claim')
  })
  it('a screen with a rule never leaves the merchant at a dead end: every screen answers', () => {
    for (const screen of SCREENS) expect(run({ screen }).id).toBeTruthy()
  })
})

describe('nextBestAction: the rules behind a flag', () => {
  it('says nothing about Ask Chhatri or the slip while their flags are off', () => {
    expect(winner({ screen: 'home' })).toBe('see_coverage')
    expect(winner({ screen: 'home', claims: [waitingForSlip] })).toBe('see_coverage')
  })

  it('opens the ask screen and the slip screen', () => {
    expect(run({ screen: 'help', features: { ask: true } }).target).toEqual({ type: 'screen', screen: 'ask' })
    expect(run({ screen: 'home', claims: [waitingForSlip], features: { slip: true } }).target).toEqual({ type: 'screen', screen: 'slip' })
  })

  it('puts the slip before a paid claim, and a dispute before the slip', () => {
    expect(winner({ screen: 'home', claims: [waitingForSlip, paid], features: { slip: true } })).toBe('send_slip')
    expect(winner({ screen: 'home', claims: [disputeOpen, waitingForSlip], features: { slip: true } })).toBe('see_dispute_case')
  })

  it('keeps Ask Chhatri below the alert and the due premium', () => {
    expect(winner({ screen: 'home', cover: cover('ACTIVE', { premium_due: true }), features: { ask: true } })).toBe('see_premium')
    expect(winner({ screen: 'home', cover: cover('NONE'), features: { ask: true } })).toBe('get_cover')
  })

  it('focuses the first unticked required box, before the price check, and only while nothing is quoted', () => {
    const box = 'buy-consent-SETTLEMENT_DEDUCTION'
    expect(run({ screen: 'buy', cover: cover('NONE'), buy: { phase: 'idle', simulated: true, consent: { firstUnticked: box } } }).target).toEqual({ type: 'focus', testId: box })
    expect(winner({ screen: 'buy', cover: cover('NONE'), buy: { phase: 'idle', simulated: true, consent: { firstUnticked: null } } })).toBe('check_price')
    expect(winner({ screen: 'buy', cover: cover('NONE'), buy: { ...quoted, consent: { firstUnticked: box } } })).toBe('pay')
  })
})

describe('nextBestAction: sentence facts and targets', () => {
  it('names the amount of the paid claim and links to why, on that decision', () => {
    const result = run({ screen: 'home', claims: [paid] })
    expect(result.params).toEqual({ amount: '₹1,380' })
    expect(result.target).toEqual({ type: 'screen', screen: 'why', decision: 'D-000142' })
  })
  it('puts the start date of a waiting cover in the language shown', () => {
    expect(run({ screen: 'home', cover: cover('WAITING') }).params).toEqual({ starts_on: '25 August' })
    expect(run({ screen: 'home', cover: cover('WAITING'), lang: 'hi' }).params).toEqual({ starts_on: '25 अगस्त' })
  })
  it('puts the dispute clock from the rules in the sentence of a wait', () => {
    expect(run({ screen: 'home', claims: [disputeOpen], slaHours: 24 }).params).toEqual({ sla_hours: 24 })
    expect(run({ screen: 'home', claims: [disputeOpen], slaHours: 48 }).params).toEqual({ sla_hours: 48 })
  })
  it('opens the claim a dispute is about', () => {
    expect(run({ screen: 'home', claims: [disputeOpen] }).target).toEqual({ type: 'screen', screen: 'claim', claim: 'CL-000001' })
    expect(run({ screen: 'claims', claims: [disputeOpen] }).target).toEqual({ type: 'screen', screen: 'claim', claim: 'CL-000001' })
  })
  it('sends a due premium to the premium section of the coverage screen, and an alert to the rain section', () => {
    expect(run({ screen: 'home', cover: cover('ACTIVE', { premium_due: true }) }).target).toEqual({ type: 'screen', screen: 'coverage', section: 'c6' })
    expect(run({ screen: 'home', cover: cover('ACTIVE', { alert_active: true, alert_id: 'A-1' }) }).target).toEqual({ type: 'screen', screen: 'coverage', section: 'c2' })
  })
  it('focuses the price check, then the pay button the screen shows (simulated or live)', () => {
    expect(run({ screen: 'buy', cover: cover('NONE'), buy: { phase: 'idle', simulated: true } }).target).toEqual({ type: 'focus', testId: 'buy-check' })
    expect(run({ screen: 'buy', cover: cover('NONE'), buy: { phase: 'quoted', simulated: true } }).target).toEqual({ type: 'focus', testId: 'buy-simulate-pay' })
    const live = run({ screen: 'buy', cover: cover('NONE'), buy: { phase: 'quoted', simulated: false } })
    expect(live.target).toEqual({ type: 'focus', testId: 'buy-pay-live' })
    expect(live.buttonKey).toBe('buy.pay')
  })
  it('sends the disagreement to the dispute button of the claim', () => {
    expect(run({ screen: 'receipt', claim: paid, claims: [paid] }).target).toEqual({ type: 'screen', screen: 'claim', claim: 'CL-000001', focus: 'claim-dispute-button' })
  })
  it('does not name a paid claim that has no decision or amount to show', () => {
    const odd = { ...paid, decision_id: null }
    expect(run({ screen: 'home', claims: [odd] }).id).toBe('see_coverage')
    expect(run({ screen: 'home', claims: [{ ...paid, amount_label: null }] }).id).toBe('see_coverage')
  })
  it('keeps no cover and no claims known as an answer: while the cover is unknown the global list says see coverage', () => {
    expect(run({ screen: 'home', cover: null }).id).toBe('see_coverage')
  })
})

describe('no next action is an offer (AC-37, X8)', () => {
  const covers = (['NONE', 'PENDING_PAYMENT', 'WAITING', 'ACTIVE', 'LAPSED', 'CANCELLED'] as const).flatMap((status) => [
    cover(status),
    cover(status, { premium_due: true }),
    cover(status, { alert_active: true, alert_id: 'A-20250818-01' }),
  ])
  const claimSets: ClaimItem[][] = [[], [paid], [referred], [disputeOpen, paid], [declined], [approvedNotCredited]]
  const buys: (NbaBuyState | undefined)[] = [undefined, { phase: 'idle', simulated: true }, quoted, { phase: 'paid', simulated: false }]

  it('returns only the closed list of kinds, whatever the cover, the claims, the alert or the screen', () => {
    let runs = 0
    for (const screen of SCREENS as readonly Screen[]) {
      for (const c of covers) {
        for (const claims of claimSets) {
          for (const buy of buys) {
            for (const open of claims.length > 0 ? [undefined, claims[0]] : [undefined]) {
              const result = nextBestAction({ ...base, screen, cover: c, claims, ...(buy ? { buy } : {}), ...(open ? { claim: open } : {}) })
              expect(NBA_KINDS).toContain(result.kind)
              runs += 1
            }
          }
        }
      }
    }
    expect(runs).toBeGreaterThan(1000)
  })

  it('has a closed kind list with no offer, loan, top-up or cross-sell in it', () => {
    expect([...NBA_KINDS].toSorted()).toEqual(['ASK', 'BUY_COVER', 'FOCUS', 'SEND_SLIP', 'VIEW', 'WAIT'])
    expect(NBA_KINDS.some((kind) => /OFFER|LOAN|TOP_UP|CROSS|UPSELL|CREDIT|PROMO/.test(kind))).toBe(false)
  })
})

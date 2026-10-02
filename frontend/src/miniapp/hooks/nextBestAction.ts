/**
 * The next-best-action rules (fs-04 section 12, H21): every screen ends in one sentence and one button, chosen by a
 * pure function from what the screen knows. The screen's own rules are checked first; the global list (S1, S8 and the
 * fallback of every other screen) decides the rest, and the first match wins. The answer is `{id, kind, sentenceKey,
 * params, target}`. `kind` is a closed list with no offer in it: a loan, a top-up or a cross-sell cannot be returned,
 * so X8 holds by construction, also while an alert is in force or a claim is open (AC-37). The sentence and the
 * button are copy keys (`nba.<rule id>` and `nba.<rule id>.btn`, copy deck 8.1); the rule numbers and facts in them
 * arrive in `params`. The rules of Wave 2 and 3 read their flags from `features` (Ask Chhatri, the slip pre-check) and
 * the consent block of the buy screen from `buy.consent`; a rule whose flag is off never matches.
 *
 * A screen does not call this directly: `useNextBest` (nextBestActionBar.tsx) runs it and registers the answer with
 * the bar above the tab bar.
 */
import type { ClaimItem, Cover } from '../../api/types'
import type { CopyKey, CopyParams } from '../lib/copy'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import type { Screen } from './useMiniappUrl'

export const NBA_KINDS = ['VIEW', 'ASK', 'BUY_COVER', 'SEND_SLIP', 'WAIT', 'FOCUS'] as const
export type NbaKind = (typeof NBA_KINDS)[number]

/** Words that would make a kind an offer. A kind that matches one of them turns `NoOfferKind` into an error. */
type OfferWords = 'OFFER' | 'LOAN' | 'TOP_UP' | 'CROSS_SELL' | 'UPSELL' | 'CREDIT' | 'PROMO'
type NoOfferKind = [Extract<NbaKind, OfferWords>] extends [never] ? true : never
/** The type-level check of AC-37: this line stops compiling the day an offer kind is added to `NBA_KINDS`. */
export const NO_OFFER_KIND: NoOfferKind = true

export type NbaRuleId =
  | 'get_cover_from_coverage'
  | 'see_claims'
  | 'home_from_coverage'
  | 'tick_consent'
  | 'check_price'
  | 'pay'
  | 'home_after_paid'
  | 'home_when_covered'
  | 'open_latest'
  | 'see_coverage_empty'
  | 'wait_for_officer'
  | 'see_why'
  | 'back_to_claims'
  | 'see_receipt'
  | 'disagree'
  | 'home_after_language'
  | 'see_dispute_case'
  | 'see_referred_claim'
  | 'send_slip'
  | 'see_coverage_waiting'
  | 'get_cover'
  | 'see_premium'
  | 'alert_notice'
  | 'ask'
  | 'see_coverage'

/** Where the button leads: a screen (and perhaps a section or a control to focus on arrival), or a control on this screen. */
export type NbaTarget =
  | { type: 'screen'; screen: Screen; claim?: string; decision?: string; section?: string; focus?: string }
  | { type: 'focus'; testId: string }

export type NbaResult = {
  id: NbaRuleId
  kind: NbaKind
  sentenceKey: Extract<CopyKey, `nba.${NbaRuleId}`>
  /** `nba.<id>.btn`, except the pay step, whose button carries the label of the button in the body (`buy.simulate` or `buy.pay`). */
  buttonKey: Extract<CopyKey, `nba.${NbaRuleId}.btn` | 'buy.simulate' | 'buy.pay'>
  params: CopyParams
  target: NbaTarget
}

/**
 * Where the buy screen is: nothing asked, a quote with a link on screen, or the payment made. `consent` is the consent
 * block of `n6_consents` (fs-07 9.5): the test id of the first required box still unticked, or null once both are ticked.
 */
export type NbaBuyState = { phase: 'idle' | 'quoted' | 'paid'; simulated: boolean; consent?: { firstUnticked: string | null } }

/** The flags the rules read (fs-04 section 4.6); a missing one is off. */
export type NbaFeatures = { ask?: boolean; slip?: boolean }

export type NbaInput = {
  screen: Screen
  lang: Lang
  /** The merchant's cover, or null while it is not known (no rule that needs it fires). */
  cover: Cover | null
  /** Newest first, as the API sends them. */
  claims: readonly ClaimItem[]
  /** The claim open on S5 to S7. */
  claim?: ClaimItem | null
  buy?: NbaBuyState
  /** The dispute clock of the rules (`dispute_sla_hours`): the sentences that promise an answer name it. */
  slaHours: number
  features?: NbaFeatures
}

type Rule = (input: NbaInput) => NbaResult | null

const HAS_COVER: ReadonlySet<Cover['status']> = new Set(['PENDING_PAYMENT', 'WAITING', 'ACTIVE'])

const isDispute = (item: ClaimItem): boolean => item.kind === 'DISPUTE'

/** An open question about a payout (a DISPUTE item whose case is still open). */
const isDisputeOpen = (item: ClaimItem): boolean => isDispute(item) && item.case_status === 'OPEN'

/** A personal claim a person still has to decide (an AREA claim is never referred). */
const isReferred = (item: ClaimItem): boolean => item.kind === 'PERSONAL' && item.outcome === 'REFERRED'

/** Paid: approved, the Paid step done, and an amount and a decision to show. Approved with the credit on its way is not paid. */
function isPaid(item: ClaimItem): boolean {
  if (isDispute(item) || item.outcome !== 'APPROVED' || item.decision_id === null || item.amount_label === null) return false
  return item.steps.some((step) => step.name === 'Paid' && step.status === 'completed')
}

/** The claim a claim item opens: its own id, or the claim a dispute is about. */
const claimIdOf = (item: ClaimItem): string | null => item.claim_id ?? item.disputed_claim_id

const screenTarget = (screen: Screen, extra: Omit<Extract<NbaTarget, { type: 'screen' }>, 'type' | 'screen'> = {}): NbaTarget => ({ type: 'screen', screen, ...extra })

function answer(id: NbaRuleId, kind: NbaKind, target: NbaTarget, params: CopyParams = {}, buttonKey?: NbaResult['buttonKey']): NbaResult {
  return { id, kind, sentenceKey: `nba.${id}`, buttonKey: buttonKey ?? `nba.${id}.btn`, params, target }
}

const claimTarget = (item: ClaimItem): NbaTarget => {
  const claim = claimIdOf(item)
  return claim === null ? screenTarget('claims') : screenTarget('claim', { claim })
}

// ------------------------------------------------------------------------------------------ screen rules

const getCoverFromCoverage: Rule = ({ cover }) =>
  cover?.status === 'NONE' ? answer('get_cover_from_coverage', 'BUY_COVER', screenTarget('buy')) : null

const seeClaims: Rule = ({ claims }) => (claims.length > 0 ? answer('see_claims', 'VIEW', screenTarget('claims')) : null)

const homeFromCoverage: Rule = () => answer('home_from_coverage', 'VIEW', screenTarget('home'))

const homeAfterPaid: Rule = ({ buy }) => (buy?.phase === 'paid' ? answer('home_after_paid', 'VIEW', screenTarget('home')) : null)

const homeWhenCovered: Rule = ({ cover }) => (cover !== null && HAS_COVER.has(cover.status) ? answer('home_when_covered', 'VIEW', screenTarget('home')) : null)

const pay: Rule = ({ buy }) => {
  if (buy?.phase !== 'quoted') return null
  return buy.simulated
    ? answer('pay', 'FOCUS', { type: 'focus', testId: 'buy-simulate-pay' }, {}, 'buy.simulate')
    : answer('pay', 'FOCUS', { type: 'focus', testId: 'buy-pay-live' }, {}, 'buy.pay')
}

/** The consent block is incomplete: go to the first required box that is still unticked (before check_price). */
const tickConsent: Rule = ({ buy }) => {
  const box = buy?.phase === 'idle' ? buy.consent?.firstUnticked : null
  return box ? answer('tick_consent', 'FOCUS', { type: 'focus', testId: box }) : null
}

const checkPrice: Rule = () => answer('check_price', 'FOCUS', { type: 'focus', testId: 'buy-check' })

const openLatest: Rule = ({ claims }) => {
  const latest = claims[0]
  return latest ? answer('open_latest', 'VIEW', claimTarget(latest)) : null
}

const seeCoverageEmpty: Rule = () => answer('see_coverage_empty', 'VIEW', screenTarget('coverage'))

/** On S5: a question about this claim is open, or this claim is with a person. */
const waitForOfficer: Rule = ({ claim, claims, slaHours }) => {
  if (!claim) return null
  const waiting = isReferred(claim) || claims.some((item) => isDisputeOpen(item) && item.disputed_claim_id !== null && item.disputed_claim_id === claim.claim_id)
  return waiting ? answer('wait_for_officer', 'WAIT', screenTarget('claims'), { sla_hours: slaHours }) : null
}

const seeWhyOfClaim: Rule = ({ claim }) => (claim && isPaid(claim) ? seeWhy(claim) : null)

const backToClaims: Rule = () => answer('back_to_claims', 'VIEW', screenTarget('claims'))

const seeReceipt: Rule = ({ claim }) => {
  const decision = claim?.decision_id
  return answer('see_receipt', 'VIEW', decision ? screenTarget('receipt', { decision }) : screenTarget('claims'))
}

const disagree: Rule = ({ claim }) => {
  const id = claim && isPaid(claim) ? claim.claim_id : null
  return id === null ? null : answer('disagree', 'FOCUS', screenTarget('claim', { claim: id, focus: 'claim-dispute-button' }))
}

const homeAfterLanguage: Rule = () => answer('home_after_language', 'VIEW', screenTarget('home'))

// ------------------------------------------------------------------------------------------ global list

function seeWhy(item: ClaimItem): NbaResult {
  return answer('see_why', 'VIEW', screenTarget('why', { decision: item.decision_id ?? '' }), { amount: item.amount_label ?? '' })
}

const seeDisputeCase: Rule = ({ claims, slaHours }) => {
  const open = claims.find(isDisputeOpen)
  return open ? answer('see_dispute_case', 'WAIT', claimTarget(open), { sla_hours: slaHours }) : null
}

const seeReferredClaim: Rule = ({ claims }) => {
  const referred = claims.find(isReferred)
  return referred ? answer('see_referred_claim', 'WAIT', claimTarget(referred)) : null
}

const seeWhyOfLatest: Rule = ({ claims }) => {
  const latest = claims[0]
  return latest && isPaid(latest) ? seeWhy(latest) : null
}

/** A personal claim that waits for the slip (its Detected step is the current one, fs-04 9.5), with the pre-check on. */
const isWaitingForSlip = (item: ClaimItem): boolean => item.kind === 'PERSONAL' && item.decision_id === null && item.steps[0]?.status === 'current'

const sendSlip: Rule = ({ claims, features }) => (features?.slip && claims.some(isWaitingForSlip) ? answer('send_slip', 'SEND_SLIP', screenTarget('slip')) : null)

const seeCoverageWaiting: Rule = ({ cover, lang }) =>
  cover?.status === 'WAITING' && cover.starts_on !== null
    ? answer('see_coverage_waiting', 'VIEW', screenTarget('coverage'), { starts_on: formatDate(cover.starts_on, lang) })
    : null

const getCover: Rule = ({ cover }) => (cover?.status === 'NONE' ? answer('get_cover', 'BUY_COVER', screenTarget('buy')) : null)

const seePremium: Rule = ({ cover }) => (cover?.premium_due ? answer('see_premium', 'VIEW', screenTarget('coverage', { section: 'c6' })) : null)

const alertNotice: Rule = ({ cover }) =>
  cover?.alert_active && cover.status === 'ACTIVE' ? answer('alert_notice', 'VIEW', screenTarget('coverage', { section: 'c2' })) : null

const ask: Rule = ({ features }) => (features?.ask ? answer('ask', 'ASK', screenTarget('ask')) : null)

/** Matches every input, so the global list always answers. */
const seeCoverage = (): NbaResult => answer('see_coverage', 'VIEW', screenTarget('coverage'))

/** Checked in this order; the first match wins. S1 and S8 use nothing else, and every screen falls back to it. */
const GLOBAL_RULES: readonly Rule[] = [seeDisputeCase, seeReferredClaim, sendSlip, seeWhyOfLatest, seeCoverageWaiting, getCover, seePremium, alertNotice, ask, seeCoverage]

/** Checked first on that screen, in this order. A screen with none of its own (S1, S8) goes straight to the global list. */
const SCREEN_RULES: Readonly<Partial<Record<Screen, readonly Rule[]>>> = {
  coverage: [getCoverFromCoverage, seeClaims, homeFromCoverage],
  buy: [homeAfterPaid, homeWhenCovered, pay, tickConsent, checkPrice],
  claims: [openLatest, seeCoverageEmpty],
  claim: [waitForOfficer, seeWhyOfClaim, backToClaims],
  why: [seeReceipt],
  receipt: [disagree],
  settings: [homeAfterLanguage],
}

function firstMatch(rules: readonly Rule[], input: NbaInput): NbaResult | null {
  for (const rule of rules) {
    const result = rule(input)
    if (result) return result
  }
  return null
}

export function nextBestAction(input: NbaInput): NbaResult {
  // `seeCoverage` ends the global list and matches everything, so there is always an answer: no screen is a dead end.
  return firstMatch(SCREEN_RULES[input.screen] ?? [], input) ?? firstMatch(GLOBAL_RULES, input) ?? seeCoverage()
}

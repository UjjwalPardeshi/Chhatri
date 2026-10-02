/**
 * Counterfactuals for the mock receipt (fs-09 section 9, H14): a sentence that says what would have changed the
 * outcome, with numbers the engine re-ran. The mock engine (`claims.ts`) is run again on a changed copy of the facts
 * and the result is kept only if it is strictly better, so `verified` is always true. The mock produces them for the
 * three golden decisions (the monsoon area payout, the approved illness claim, the referred mismatch claim) and for
 * the same kinds of decision made by the policy engine; an officer's decision carries none. FLIP_FROM_DECLINED,
 * ZONE_NO_TRIGGER and EXPLAIN_ONLY have no mock decision that needs them. An LLM never writes any of this text.
 * The Hindi lines are proposed and need a native review (fs-09 9.6).
 */
import type { Check, Counterfactual, CounterfactualChange, Source } from '../../api/types'
import { formatInr } from '../../lib/money'
import { areaExplanation, outcomeOf, personalExplanation } from '../claims'
import { POLICY_RULES } from '../fixtures'
import { alertSource, checkSources, explanationOf, salesDay, salesIndex, type Provenance } from './provenance'

type Flip = {
  field: string
  needed: string
  actionable: boolean
  observed: (check: Check) => string
  en: string
  hi: string
}

const pick = (check: Check, pattern: RegExp): string => pattern.exec(check.observed ?? '')?.[1] ?? check.observed ?? ''

/** The soft checks the mock can fail, and the single honest change for each (fs-09 9.3). Names are never coached. */
const FLIPS: Readonly<Record<string, Flip>> = Object.freeze({
  SLIP_READABLE: {
    field: 'slip_confidence',
    needed: '0.80 or more',
    actionable: true,
    observed: (c) => pick(c, /confidence ([\d.]+)/),
    en: 'the slip had been clear enough to read (confidence 0.80 or more)',
    hi: 'पर्ची साफ़ पढ़ी जा सकती (भरोसा 0.80 या उससे ज़्यादा)',
  },
  NAME_MATCHES_KYC: {
    field: 'slip_name_score',
    needed: '85 or more',
    actionable: false,
    observed: (c) => pick(c, /score (\d+)/),
    en: 'the name on the slip had matched your KYC name (score 85 or more)',
    hi: 'पर्ची का नाम आपके KYC नाम से मिलता (स्कोर 85 या उससे ज़्यादा)',
  },
  DATES_MATCH: {
    field: 'slip_stay',
    needed: 'covers the claimed days',
    actionable: false,
    observed: (c) => c.observed ?? '',
    en: 'the dates on the slip had covered the claimed days',
    hi: 'पर्ची की तारीख़ें दावे के दिनों को ढक लेतीं',
  },
})

const unsure = (check: Check): boolean => check.severity === 'SOFT' && (check.status === 'FAIL' || check.status === 'UNSURE')

/** Distinct sources, first seen first. */
function distinct(sources: readonly Source[]): Source[] {
  const seen = new Set<string>()
  return sources.filter((s) => (seen.has(s.ref) ? false : Boolean(seen.add(s.ref))))
}

/** REFERRED: flip every failing soft check together, re-run the outcome, keep it if the claim would have been paid. */
function flipFromReferred(p: Provenance): Counterfactual | null {
  const { decision } = p
  const targets = decision.checks.filter((c) => unsure(c) && c.code in FLIPS)
  if (targets.length === 0 || targets.length !== decision.checks.filter(unsure).length) return null
  const flipped = decision.checks.map((c): Check => (targets.includes(c) ? { ...c, status: 'PASS' } : c))
  const outcome = outcomeOf(flipped)
  if (outcome !== 'APPROVED') return null
  const changes: CounterfactualChange[] = targets.map((c) => ({ check_code: c.code, field: FLIPS[c.code].field, observed: FLIPS[c.code].observed(c), needed: FLIPS[c.code].needed }))
  const ifPart = (lang: 'en' | 'hi', joiner: string) => targets.map((c) => FLIPS[c.code][lang]).join(joiner)
  const amount = explanationOf(decision).amount_paise
  return {
    id: 'CF-1',
    kind: 'FLIP_FROM_REFERRED',
    actionable: targets.some((c) => FLIPS[c.code].actionable),
    changes,
    result: { outcome, amount_paise: amount, amount_label: formatInr(amount) },
    verified: true,
    text_en: `If ${ifPart('en', ' and ')}, this claim would have been paid automatically.`,
    text_hi: `अगर ${ifPart('hi', ' और ')}, तो यह दावा अपने-आप मंज़ूर हो जाता।`,
    sources: distinct(targets.flatMap((c) => checkSources(c.code, p).slice(0, 1))),
  }
}

/** APPROVED: what one more point of area drop, or one more claimed day, would add (re-run through the mock engine). */
function amountSensitivity(p: Provenance): Counterfactual | null {
  const { decision } = p
  const ex = explanationOf(decision)
  const day = decision.decided_at.slice(0, 10)
  const area = ex.drop_pct !== null
  if (!area && ex.days + 1 > POLICY_RULES.personal.max_auto_days) return null
  const next = ex.drop_pct !== null ? areaExplanation(day, ex.expected_day_paise, ex.drop_pct + 1) : personalExplanation(day, ex.expected_day_paise, ex.days + 1)
  if (next.amount_paise <= decision.amount_paise) return null
  const gain = formatInr(next.amount_paise - decision.amount_paise)
  const maxDays = POLICY_RULES.personal.max_auto_days
  const sources = (area ? [salesIndex(p, 'C2'), alertSource(p, 'C2')] : [salesDay(p, 'C3')]).filter((x): x is Source => x !== null)
  const change: CounterfactualChange = area
    ? { check_code: null, field: 'drop_pct', observed: String(ex.drop_pct), needed: String((ex.drop_pct ?? 0) + 1) }
    : { check_code: null, field: 'days', observed: String(ex.days), needed: String(ex.days + 1) }
  return {
    id: 'CF-1',
    kind: 'AMOUNT_SENSITIVITY',
    actionable: false,
    changes: [change],
    result: { outcome: outcomeOf(decision.checks), amount_paise: next.amount_paise, amount_label: formatInr(next.amount_paise) },
    verified: true,
    // The backend's CF_AMOUNT_ONE_POINT and CF_AMOUNT_ONE_DAY lines (conversation/messages.py).
    text_en: area ? `One more point of area drop would have added about ${gain}.` : `Each extra qualifying day adds ${gain}, up to ${maxDays} days without a review.`,
    text_hi: area ? `इलाके की गिरावट एक प्रतिशत और होती, तो लगभग ${gain} और जुड़ते।` : `हर अतिरिक्त पात्र दिन के ${gain} जुड़ते हैं, बिना समीक्षा के ज़्यादा से ज़्यादा ${maxDays} दिन तक।`,
    sources,
  }
}

export function counterfactualsFor(p: Provenance): Counterfactual[] {
  if (p.decision.decided_by !== 'policy-engine') return []
  const found = p.decision.outcome === 'REFERRED' ? flipFromReferred(p) : p.decision.outcome === 'APPROVED' ? amountSensitivity(p) : null
  return found ? [found] : []
}

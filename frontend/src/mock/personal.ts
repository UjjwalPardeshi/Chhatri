/**
 * Mock personal claims (SPEC §9.2 personal checks, §9.3 outcome, §13.5 silent check-in flow,
 * §17.2 illness / illness_mismatch). The slip reader recognises the three committed sample slips
 * by name; any other photo is unreadable (SLIP_READABLE UNSURE ⇒ REFERRED, "slip unclear → human").
 */
import type { Check, SlipEvidence } from '../api/types'
import { MSG, type Bilingual } from './catalogue'
import { announceSoundbox } from './area'
import { openReviewCase } from './cases'
import { check, decide, personalExplanation, schedulePayout } from './claims'
import type { MockMerchant } from './fixtures'
import type { MockRuntime } from './runtime'
import { addDays } from './scenarios'

export const NAME_MATCH_MIN = 85
export const SLIP_CONFIDENCE_MIN = 0.8

type SlipRead = Omit<SlipEvidence, 'media_url'> & { name_score: number | null }

export const SAMPLE_SLIPS: Readonly<Record<string, SlipRead>> = Object.freeze({
  'anil_admission_slip.png': {
    patient_name: 'Anil R. Jadhav',
    admission_date: '2025-08-20',
    discharge_date: null,
    hospital_name: 'KEM Hospital, Parel',
    document_type: 'admission_slip',
    confidence: 0.94,
    source: 'simulated',
    name_score: 100,
  },
  'mismatch_admission_slip.png': {
    patient_name: 'Sunil Pawar',
    admission_date: '2025-08-20',
    discharge_date: null,
    hospital_name: 'KEM Hospital, Parel',
    document_type: 'admission_slip',
    confidence: 0.93,
    source: 'simulated',
    name_score: 41,
  },
  'blurry_slip.png': {
    patient_name: null,
    admission_date: null,
    discharge_date: null,
    hospital_name: null,
    document_type: 'admission_slip',
    confidence: 0.41,
    source: 'simulated',
    name_score: null,
  },
})

const UNREADABLE: SlipRead = { ...SAMPLE_SLIPS['blurry_slip.png'], document_type: null, confidence: 0.3 }

function personalChecks(slip: SlipRead, silentDay: string): Check[] {
  const readable = slip.document_type !== null && slip.confidence >= SLIP_CONFIDENCE_MIN
  const nameStatus = slip.name_score === null ? 'UNSURE' : slip.name_score >= NAME_MATCH_MIN ? 'PASS' : 'FAIL'
  const datesStatus = slip.admission_date === null ? 'UNSURE' : slip.admission_date <= silentDay ? 'PASS' : 'FAIL'
  const nameObserved = slip.patient_name ? `"${slip.patient_name}" · score ${slip.name_score}` : 'no name read'
  return [
    check('COVER_IN_FORCE', 'HARD', 'PASS', 'Cover active', 'ACTIVE since 1 Jun 2025', 'ACTIVE on event date'),
    check('PREMIUM_PREPAID', 'HARD', 'PASS', 'Premium prepaid', 'prepaid through 21 Aug 2025', `≥ ${silentDay}`),
    check('SILENCE_VERIFIED', 'HARD', 'PASS', 'Shop silent on the claimed day', `${silentDay}: 0 transactions`, 'every claimed day silent'),
    check('SLIP_READABLE', 'SOFT', readable ? 'PASS' : slip.document_type ? 'UNSURE' : 'FAIL', 'Slip readable', `${slip.document_type ?? 'unknown'} · confidence ${slip.confidence.toFixed(2)}`, `medical slip, ≥ ${SLIP_CONFIDENCE_MIN.toFixed(2)}`),
    check('NAME_MATCHES_KYC', 'SOFT', nameStatus, 'Name matches KYC', nameObserved, `≥ ${NAME_MATCH_MIN} vs KYC`),
    check('DATES_MATCH', 'SOFT', datesStatus, 'Dates match the silent days', slip.admission_date ? `admitted ${slip.admission_date}` : 'no admission date', `admitted on or before ${silentDay}`),
    check('WITHIN_AUTO_LIMIT', 'SOFT', 'PASS', 'Within the automatic limit', '1 day', '≤ 3 days'),
    check('NOT_ALREADY_PAID', 'HARD', 'PASS', 'Not already paid', 'no personal payout for this date', 'none'),
    check('WITHIN_ANNUAL_LIMIT', 'HARD', 'PASS', 'Within the annual limit', '₹0 paid this year', '≤ ₹30,000'),
  ]
}

function referralMessage(checks: readonly Check[]): Bilingual {
  const failing = checks.find((c) => c.severity === 'SOFT' && c.status !== 'PASS')
  return failing?.code === 'NAME_MATCHES_KYC' ? MSG.slipToHuman : MSG.slipUnreadable
}

export function submitSlip(rt: MockRuntime, merchant: MockMerchant, mediaUrl: string, sample: string | null): void {
  const read = (sample ? SAMPLE_SLIPS[sample] : undefined) ?? UNREADABLE
  const silentDay = addDays(rt.scenario.day, -1)
  const claimId = rt.nextId('CL')
  rt.conversations.set(merchant.id, { ...rt.conversation(merchant.id), claimId })
  rt.record('ai-agent', 'slip.read', 'claim', claimId, { patient_name: read.patient_name, confidence: read.confidence })
  const checks = personalChecks(read, silentDay)
  const failing = checks.find((c) => c.severity === 'SOFT' && c.status !== 'PASS')
  const decision = decide(rt, {
    claimId,
    merchantId: merchant.id,
    checks,
    explanation: personalExplanation(silentDay, merchant.expected_day_paise, 1),
    decidedBy: 'policy-engine',
    referral: failing ? `${failing.code}: ${failing.label_en} (${failing.observed})` : null,
  })
  if (decision.outcome === 'APPROVED') {
    rt.addFeed('decision', `Personal claim approved for ${merchant.shop_name} · ${decision.amount_label}`, { merchant_id: merchant.id })
    payPersonal(rt, merchant, decision, MSG.personalPaid(merchant.owner_name_hi, merchant.owner_first_en, decision.amount_label))
    return
  }
  const { name_score: nameScore, ...extraction } = read
  const slip: SlipEvidence = { ...extraction, media_url: mediaUrl }
  const opened = openReviewCase(rt, merchant, decision, { slip, nameScore, silentDay })
  rt.addFeed('case', `Case ${opened.id} opened: ${merchant.shop_name} slip needs a claims officer`, { merchant_id: merchant.id })
  rt.send(merchant.id, { kind: 'TEXT', text: referralMessage(checks) })
  rt.send(merchant.id, { kind: 'CASE_CHIP', text: MSG.caseChip(opened.id), meta: { case_id: opened.id } })
}

/** Pays an APPROVED personal decision: credit +4 with `paidText`, card (badge per backend catalogue) and Soundbox; pause +5. */
export const PERSONAL_BADGE = 'One photo, no forms'
export const OFFICER_BADGE = 'Approved by a claims officer'

export function payPersonal(rt: MockRuntime, merchant: MockMerchant, decision: Parameters<typeof schedulePayout>[1], paidText: Bilingual, badge = PERSONAL_BADGE): void {
  schedulePayout(rt, decision, merchant, {
    onCredited: (payout) => {
      rt.send(merchant.id, { kind: 'TEXT', text: paidText })
      rt.send(merchant.id, {
        kind: 'PAYOUT_CARD',
        text: null,
        card: { amount_label: payout.amount_label, subtitle_hi: MSG.payoutCard.hi, subtitle_en: MSG.payoutCard.en, badge },
      })
      announceSoundbox(rt, merchant, payout.amount_label)
      rt.addFeed('payout', `${payout.amount_label} credited to ${merchant.shop_name} with the settlement`, { merchant_id: merchant.id })
      rt.setKpis({ total_paid_paise: rt.kpis.total_paid_paise + payout.amount_paise, shops_paid: rt.kpis.shops_paid + 1 })
    },
    onPaused: (text) => {
      rt.send(merchant.id, { kind: 'TEXT', text })
      rt.setKpis({ instalments_paused: rt.kpis.instalments_paused + 1 })
    },
  })
}

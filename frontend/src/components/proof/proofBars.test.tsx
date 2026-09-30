/** Backtest proof wording (deck slide 11, SPEC §18): the deck's words, backed only by API numbers. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { BacktestReport, BacktestTrigger } from '../../api/types'
import { comparisonVerdict, humanReviewLabel, humanReviewDetail, ProofFacts, ProofPairs, PROOF_MEASURES } from './ProofBars'

const trigger = (name: BacktestTrigger['name'], recall: number, fp: number) =>
  ({ name, recall, false_positive_rate: fp, real_drops: 148, real_drops_paid: Math.round(recall * 148), payouts: 125, payouts_no_real_drop: Math.round(fp * 125), trigger_to_money: 'same day · 4 min', documents_per_area_claim: 0 }) as BacktestTrigger
const PERSONAL: BacktestReport['personal'] = { claims: 844, auto_paid: 485, referred: 359, referred_share: 0.4254 }

describe('backtest proof wording', () => {
  it('reads each measure like deck slide 11, from the two triggers only', () => {
    const [recall, falsePositives] = PROOF_MEASURES
    const chhatri = trigger('chhatri', 0.6, 0.29)
    const weather = trigger('weather_only', 0.33, 0.85)
    expect(comparisonVerdict(recall, chhatri, weather)).toBe('More than a weather-only trigger')
    expect(comparisonVerdict(falsePositives, chhatri, weather)).toBe('Fewer than a weather-only trigger')
    expect(comparisonVerdict(recall, weather, chhatri)).toBe('Fewer than a weather-only trigger')
    expect(comparisonVerdict(recall, chhatri, chhatri)).toBe('The same as a weather-only trigger')
  })

  it('says “all of them” for doubtful claims, with the referred and auto-paid counts the API gives', () => {
    expect(humanReviewLabel(PERSONAL)).toBe('All of them')
    expect(humanReviewDetail(PERSONAL)).toBe('359 of 844 personal claims sent to a human · 485 clean claims paid automatically')
    expect(humanReviewLabel({ ...PERSONAL, referred: 0, auto_paid: 844 })).toBe('None were doubtful')
  })

  it('renders the verdicts and facts', () => {
    render(
      <>
        <ProofPairs chhatri={trigger('chhatri', 0.6, 0.29)} weather={trigger('weather_only', 0.33, 0.85)} />
        <ProofFacts chhatri={trigger('chhatri', 0.6, 0.29)} personal={PERSONAL} />
      </>,
    )
    expect(screen.getByText('More than a weather-only trigger')).toBeTruthy()
    expect(screen.getByText('Fewer than a weather-only trigger')).toBeTruthy()
    expect(screen.getByText('All of them')).toBeTruthy()
    expect(screen.queryByText(/100%/)).toBeNull()
  })
})

/** Overview building blocks: reveal-on-scroll, chart geometry and the deck story data. */
import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LAUNCHES, LIVE_TESTS, TIME_TO_MONEY } from '../../content/deck'
import { HERO_THREAD, JOURNEYS, STORY } from '../../content/story'
import { barWidthPct, CHART_MAX_DAYS } from './Problem'
import { pctLabel, PROOF_MEASURES } from './Proof'
import { RevealSection } from './Reveal'

type Callback = (entries: { isIntersecting: boolean }[]) => void

describe('RevealSection', () => {
  it('shows content at once without IntersectionObserver', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    render(<RevealSection label="x">hello</RevealSection>)
    expect(screen.getByRole('region', { name: 'x' }).className).toContain('is-in')
  })

  it('reveals when the section scrolls into view, then stops observing', () => {
    const observers: { cb: Callback; disconnect: ReturnType<typeof vi.fn<() => void>> }[] = []
    class FakeObserver {
      cb: Callback
      disconnect = vi.fn<() => void>()
      constructor(cb: Callback) {
        this.cb = cb
        observers.push(this)
      }
      observe(): void {}
    }
    vi.stubGlobal('IntersectionObserver', FakeObserver)
    render(<RevealSection label="y">story</RevealSection>)
    const region = screen.getByRole('region', { name: 'y' })
    expect(region.className).not.toContain('is-in')
    act(() => observers[0].cb([{ isIntersecting: false }]))
    expect(region.className).not.toContain('is-in')
    act(() => observers[0].cb([{ isIntersecting: true }]))
    expect(region.className).toContain('is-in')
    expect(observers[0].disconnect).toHaveBeenCalled()
  })
})

describe('deck content', () => {
  it('draws wait bars relative to the longest wait', () => {
    expect(CHART_MAX_DAYS).toBe(60)
    expect(barWidthPct(TIME_TO_MONEY[0])).toBe(100)
    expect(Math.round(barWidthPct(TIME_TO_MONEY[1]))).toBe(93)
  })

  it('formats the backtest measures', () => {
    expect(pctLabel(0.906)).toBe('91%')
    const t = { recall: 0.5, false_positive_rate: 0.25, real_drops_paid: 1, real_drops: 2, payouts_no_real_drop: 1, payouts: 4 } as Parameters<(typeof PROOF_MEASURES)[0]['value']>[0]
    expect(PROOF_MEASURES.map((m) => [m.value(t), m.detail(t)])).toEqual([
      [0.5, '1 of 2'],
      [0.25, '1 of 4'],
    ])
  })

  it('uses the SPEC §13.4 strings and golden facts in the story phones', () => {
    expect(HERO_THREAD.map((m) => m.kind)).toEqual(['TEXT', 'PAYOUT_CARD', 'VOICE', 'TEXT'])
    expect(HERO_THREAD[1].card?.amount_label).toBe(STORY.areaAmount)
    expect(HERO_THREAD[3].text_en).toBe('Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales.')
    expect(HERO_THREAD[2].meta).toEqual({ voice_source: 'browser-simulated', duration_s: 4, transcript: 'मुझे इतने ही पैसे क्यों मिले?' })
    const [rain, illness, questions] = JOURNEYS
    expect(rain.thread[2].text_hi).toBe('कल की ₹600 की किस्त रोक दी गई है।')
    expect(rain.soundbox?.text_hi).toBe('Paytm par ₹1,380 prapt hue — Chhatri se')
    expect(illness.thread.at(-1)?.card?.amount_label).toBe('₹1,500')
    expect(questions.thread.at(-1)?.text_en).toBe('Sent to a claims officer · case C-2291')
  })

  it('points every live test at its SPEC §17.2 scenario and demo merchant (B5)', () => {
    expect(LIVE_TESTS.map((t) => [t.tag, LAUNCHES[t.launch].scenario, LAUNCHES[t.launch].to])).toEqual([
      ['EXPLAINED', 'monsoon', '/merchant/S-0142'],
      ['HUMAN', 'illness_mismatch', '/merchant/S-0142'],
      ['BLOCKED', 'buy_cover', '/merchant/S-0907'],
    ])
  })
})

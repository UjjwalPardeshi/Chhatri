/** The trigger-to-payout moment card (fs-08 13.4, AC-MC-01 to AC-MC-03): one state for each beat, and absent outside the slow window. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { AreaTrigger, ClockState, Kpis, ScenarioName, ZoneSnapshot } from '../../api/types'
import { MomentCard, momentOf, type MomentInput } from './MomentCard'

const at = (hhmm: string) => `2025-08-19T${hhmm}:00+05:30`

function clock(now: string, over: Partial<ClockState> = {}): ClockState {
  return {
    now: at(now),
    scenario: 'monsoon',
    scenario_title: 'Monsoon replay',
    running: false,
    speed: 1,
    start: at('08:00'),
    end: at('20:00'),
    label: `Mumbai · monsoon replay · ${now} · simulated`,
    ...over,
  }
}

function trigger(zoneId: string, shops: number): AreaTrigger {
  return {
    id: `T-${zoneId}`,
    zone_id: zoneId,
    alert_id: 'A-1',
    window_start: at('14:00'),
    window_end: at('17:00'),
    index_pct: 37,
    drop_pct: 63,
    hourly_index_pct: [40, 38, 33],
    lower_bound_pct: 60,
    shops_in_index: shops,
    fired_at: at('17:00'),
  }
}

function zone(id: string, status: ZoneSnapshot['status']): ZoneSnapshot {
  return { zone_id: id, ward: 'K', name: id, shops: 40, index_pct: 50, live_index_pct: 50, lower_bound_pct: 60, status, hours_below: 2, alert: null, label: id }
}

const TRIGGERS = [trigger('Z3', 141), trigger('Z7', 46), trigger('Z12', 125)]
const NO_MONEY: Kpis = { zones_triggered: 3, shops_paid: 0, trigger_to_money_min: null, total_paid_paise: 0, total_paid_label: '₹0', instalments_paused: 0 }
const PAID: Kpis = { zones_triggered: 3, shops_paid: 312, trigger_to_money_min: 4, total_paid_paise: 42_542_000, total_paid_label: '₹4,25,420', instalments_paused: 0 }
const PAUSED: Kpis = { ...PAID, instalments_paused: 123 }
const WATCHING = [zone('Z3', 'watch'), zone('Z7', 'watch'), zone('Z12', 'watch'), zone('Z9', 'slow_day')]

function input(now: string, over: Partial<MomentInput> = {}): MomentInput {
  return { clock: clock(now), zones: WATCHING, triggers: TRIGGERS, kpis: NO_MONEY, railDelayMinutes: 4, ...over }
}

const BEATS: Record<string, MomentInput> = {
  '16:58': input('16:58', { triggers: [], kpis: { ...NO_MONEY, zones_triggered: 0 } }),
  '17:00': input('17:00'),
  '17:02': input('17:02'),
  '17:04': input('17:04', { kpis: PAID }),
  '17:05': input('17:05', { kpis: PAUSED }),
  '17:06': input('17:06', { kpis: PAUSED }),
}

const line = () => document.querySelector('.moment__line')?.textContent
const card = () => document.querySelector('.moment') as HTMLElement | null
const cursor = () => (document.querySelector('.moment__cursor') as HTMLElement).style.left

describe('the moment card, beat by beat', () => {
  it('16:58: the slow window starts and the card waits for the trigger', () => {
    render(<MomentCard {...BEATS['16:58']} />)
    expect(card()?.dataset.state).toBe('waiting')
    expect(line()).toBe('Waiting for the 17:00 trigger check · 3 zones on watch')
    expect(cursor()).toBe('0%')
  })

  it('17:00: triggered, paying 312 shops, credit due 17:04 (fs-08 13.4)', () => {
    render(<MomentCard {...BEATS['17:00']} />)
    expect(card()?.dataset.state).toBe('paying')
    expect(line()).toBe('Triggered at 17:00 · paying 312 shops · credit due 17:04')
    expect(cursor()).toBe('25%')
  })

  it('17:02: still paying, and the cursor sits between the 17:00 and 17:04 ticks (AC-MC-01)', () => {
    render(<MomentCard {...BEATS['17:02']} />)
    expect(card()?.dataset.state).toBe('paying')
    expect(line()).toBe('Triggered at 17:00 · paying 312 shops · credit due 17:04')
    const ticks = [...document.querySelectorAll<HTMLElement>('.moment__tick')].map((t) => Number.parseFloat(t.style.left))
    expect(ticks).toEqual([25, 75, 87.5])
    expect(Number.parseFloat(cursor())).toBeGreaterThan(ticks[0])
    expect(Number.parseFloat(cursor())).toBeLessThan(ticks[1])
  })

  it('17:04: the money has landed', () => {
    render(<MomentCard {...BEATS['17:04']} />)
    expect(card()?.dataset.state).toBe('credited')
    expect(line()).toBe('Credited at 17:04 · ₹4,25,420 to 312 shops')
    expect(cursor()).toBe('75%')
  })

  it('17:05: the instalments are paused, with no holiday line until that data exists', () => {
    render(<MomentCard {...BEATS['17:05']} />)
    expect(card()?.dataset.state).toBe('instalments')
    expect(line()).toBe('123 instalments paused · ₹4,25,420 to 312 shops')
    expect(cursor()).toBe('87.5%')
    expect(screen.queryByText(/holiday requests/)).toBeNull()
  })

  it('17:06: the replay is held at the end of the window and the card stays, marked as paused', () => {
    render(<MomentCard {...BEATS['17:06']} />)
    expect(card()?.dataset.state).toBe('instalments')
    expect(card()?.dataset.held).toBe('true')
    expect(screen.getByText('Replay paused at 17:06')).toBeTruthy()
    expect(cursor()).toBe('100%')
    expect(line()).toBe('123 instalments paused · ₹4,25,420 to 312 shops')
  })

  it('is not marked as held inside the window', () => {
    render(<MomentCard {...BEATS['17:05']} />)
    expect(card()?.dataset.held).toBe('false')
    expect(screen.queryByText(/Replay paused/)).toBeNull()
  })
})

describe('where the card is absent', () => {
  it('17:06 while the replay is still running, the minute the window closes', () => {
    expect(momentOf({ ...BEATS['17:06'], clock: clock('17:06', { running: true }) })).toBeNull()
    const { container } = render(<MomentCard {...BEATS['17:06']} clock={clock('17:06', { running: true })} />)
    expect(container.innerHTML).toBe('')
  })

  it('keeps the card through the pause that is being asked for at 17:06, so it never blinks at the hold', () => {
    const running = clock('17:06', { running: true })
    expect(momentOf({ ...BEATS['17:06'], clock: running, pausing: true })?.held).toBe(true)
    expect(momentOf({ ...BEATS['17:06'], clock: running, pausing: false })).toBeNull()
    expect(momentOf({ ...input('17:07', { kpis: PAUSED }), clock: clock('17:07', { running: true }), pausing: true })).toBeNull()
  })

  it('18:00 and before the window (AC-MC-02)', () => {
    expect(momentOf(input('18:00', { kpis: PAUSED }))).toBeNull()
    expect(momentOf(input('16:57', { triggers: [] }))).toBeNull()
    const { container } = render(<MomentCard {...input('18:00', { kpis: PAUSED })} />)
    expect(container.innerHTML).toBe('')
  })

  it('every scenario without a slow window, illness included (AC-MC-03)', () => {
    const scenarios: ScenarioName[] = ['illness', 'illness_mismatch', 'buy_cover']
    for (const scenario of scenarios) expect(momentOf(input('17:02', { clock: clock('17:02', { scenario }) }))).toBeNull()
    expect(momentOf(input('17:02', { clock: clock('17:02', { scenario: null }) }))).toBeNull()
    const { container } = render(<MomentCard {...input('17:02', { clock: clock('17:02', { scenario: 'illness' }) })} />)
    expect(container.innerHTML).toBe('')
  })
})

describe('numbers come from the data, and a missing number leaves its words out', () => {
  it('words the credit time from the published rail delay, and drops it while the policy is unknown', () => {
    render(<MomentCard {...input('17:01', { railDelayMinutes: 5 })} />)
    expect(line()).toBe('Triggered at 17:00 · paying 312 shops · credit due 17:05')
    expect(momentOf(input('17:01', { railDelayMinutes: null }))?.parts).toEqual(['Triggered at 17:00', 'paying 312 shops'])
  })

  it('counts the shops in the triggered zones, and one zone as one', () => {
    expect(momentOf(input('17:01', { triggers: [trigger('Z7', 46)] }))?.parts[1]).toBe('paying 46 shops')
    expect(momentOf(input('17:01', { triggers: [trigger('Z7', 1)] }))?.parts[1]).toBe('paying 1 shop')
  })

  it('says "1 zone on watch" and says nothing about watch when no zone is', () => {
    expect(momentOf(input('16:59', { triggers: [], zones: [zone('Z7', 'watch')] }))?.parts).toEqual(['Waiting for the 17:00 trigger check', '1 zone on watch'])
    expect(momentOf(input('16:59', { triggers: [], zones: [zone('Z7', 'normal')] }))?.parts).toEqual(['Waiting for the 17:00 trigger check'])
  })

  it('uses the pending payout count of the ops summary when H8 provides it', () => {
    render(<MomentCard {...input('17:02')} ops={{ pendingPayouts: 310 }} />)
    expect(line()).toBe('Triggered at 17:00 · paying 310 shops · credit due 17:04')
  })

  it('says the lender\'s answers instead of the paused count when H8 provides them (fs-08 13.4), with every outcome that is not zero', () => {
    const base = input('17:05', { kpis: PAUSED })
    expect(momentOf({ ...base, ops: { holidayRequests: { GRANTED: 123, REFUSED: 0, NO_RESPONSE: 0, REQUESTED: 0 } } })?.parts).toEqual(['123 holiday requests, 123 granted'])
    expect(momentOf({ ...base, ops: { holidayRequests: { GRANTED: 120, REFUSED: 2, NO_RESPONSE: 1, REQUESTED: 0 } } })?.parts[0]).toBe('123 holiday requests, 120 granted, 2 refused, 1 no answer')
    expect(momentOf({ ...base, ops: { holidayRequests: null } })?.parts).toHaveLength(2)
    expect(momentOf({ ...base, ops: null })?.parts).toHaveLength(2)
  })

  it('says one instalment in the singular', () => {
    expect(momentOf(input('17:05', { kpis: { ...PAUSED, instalments_paused: 1 } }))?.parts[0]).toBe('1 instalment paused')
  })

  it('leaves the credit time out while the kpis cannot tell it, rather than quoting the replay clock', () => {
    expect(momentOf(input('17:05', { kpis: { ...PAID, trigger_to_money_min: null } }))?.parts).toEqual(['Credited', '₹4,25,420 to 312 shops'])
    expect(momentOf(input('17:05', { kpis: PAID }))?.parts[0]).toBe('Credited at 17:04')
  })
})

describe('the track', () => {
  it('carries the ticks of the chapters inside the window, labelled in words, and tells the cursor in words too', () => {
    render(<MomentCard {...BEATS['17:02']} />)
    expect([...document.querySelectorAll('.moment__label')].map((l) => l.textContent)).toEqual(['Trigger', 'Paid', 'Instalment'])
    expect([...document.querySelectorAll<HTMLElement>('.moment__tick')].map((t) => t.dataset.passed)).toEqual(['true', 'false', 'false'])
    expect(screen.getByRole('progressbar', { name: 'Replay at 17:02, in the window 16:58 to 17:06' })).toBeTruthy()
  })

  it('end-aligns a label whose centre would run off the track', () => {
    render(<MomentCard {...BEATS['17:05']} />)
    const labels = [...document.querySelectorAll<HTMLElement>('.moment__label')]
    expect(labels.map((l) => l.dataset.align)).toEqual(['centre', 'centre', 'end'])
    expect(labels[2].style.left).toBe('')
  })

  it('names itself for assistive technology and keeps its changes polite', () => {
    render(<MomentCard {...BEATS['17:00']} />)
    expect(screen.getByRole('region', { name: 'Trigger to payout' })).toBe(card())
    const live = document.querySelector('[aria-live="polite"]')
    expect(live?.contains(document.querySelector('.moment__line'))).toBe(true)
  })

  it('keeps one live region from beat to beat, so the next beat is announced and not swapped in silently', () => {
    const { rerender } = render(<MomentCard {...BEATS['17:02']} />)
    const live = document.querySelector('[aria-live="polite"]')
    rerender(<MomentCard {...BEATS['17:04']} />)
    expect(document.querySelector('[aria-live="polite"]')).toBe(live)
    expect(live?.textContent).toBe('Credited at 17:04 · ₹4,25,420 to 312 shops')
    rerender(<MomentCard {...BEATS['17:06']} />)
    expect(document.querySelector('[aria-live="polite"]')).toBe(live)
    expect(live?.querySelector('.moment__line')?.textContent).toBe('123 instalments paused · ₹4,25,420 to 312 shops')
    expect(live?.querySelector('.visually-hidden')?.textContent).toBe('Replay paused at 17:06')
  })
})

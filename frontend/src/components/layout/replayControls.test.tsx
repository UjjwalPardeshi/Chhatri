/** Replay controls (SPEC §17.1 clock, §17.2 story moments, §19.2 ClockState, B5 demo merchants). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ClockState, IntegrationStatus } from '../../api/types'
import { CHAPTERS, inWindow, minuteBefore, minuteOfDay, SLOW_WINDOWS } from '../../content/chapters'
import { slowDecision, type SlowMemory } from '../../state/useSlowNearPayout'
import { labelsFit, layoutChapters } from './chapterLayout'
import { clockParts, splitClockLabel } from './ClockLabel'
import { phoneMerchant } from './Header'
import { liveBrands, MAX_LIVE_CHIPS } from './IntegrationBadges'
import { chapterPct, Scrubber } from './Scrubber'

const at = (hhmm: string) => `2025-08-19T${hhmm}:00+05:30`
const CLOCK: ClockState = {
  now: at('16:00'),
  scenario: 'monsoon',
  scenario_title: 'Monsoon replay',
  running: false,
  speed: 6,
  start: at('08:00'),
  end: at('20:00'),
  label: 'Mumbai · monsoon replay · 16:00 · simulated',
}
const EMPTY: SlowMemory = { saved: null, overridden: false }
const status = (name: IntegrationStatus['name'], mode: IntegrationStatus['mode']): IntegrationStatus => ({ name, mode, detail: '' })
const WINDOW = SLOW_WINDOWS.monsoon

describe('chapter times', () => {
  it('reads HH:MM and lands a minute before a moment', () => {
    expect(minuteOfDay('17:04')).toBe(1024)
    expect(minuteOfDay('5:04')).toBeNull()
    expect(minuteBefore('17:00')).toBe('16:59')
    expect(minuteBefore('00:00')).toBe('23:59')
    expect(() => minuteBefore('later')).toThrow(/not an HH:MM/)
  })

  it('tells whether a time is inside the slow window', () => {
    expect(WINDOW).not.toBeNull()
    if (!WINDOW) return
    expect(inWindow('16:57', WINDOW)).toBe(false)
    expect(inWindow('16:58', WINDOW)).toBe(true)
    expect(inWindow('17:05', WINDOW)).toBe(true)
    expect(inWindow('17:06', WINDOW)).toBe(false)
    expect(SLOW_WINDOWS.buy_cover).toBeNull()
  })

  it('places chapters on the scenario span', () => {
    expect(chapterPct(CLOCK, '14:00')).toBe(50)
    expect(chapterPct(CLOCK, '07:00')).toBeNull()
    expect(CHAPTERS.monsoon.map((c) => c.at)).toEqual(['14:00', '17:00', '17:04', '17:05'])
  })
})

describe('chapter label layout', () => {
  it('fans out labels whose ticks are a minute apart and keeps them inside the track', () => {
    const lefts = layoutChapters(
      [
        { x: 100, w: 60 },
        { x: 104, w: 60 },
        { x: 106, w: 60 },
      ],
      400,
    )
    expect(lefts[1] - lefts[0]).toBeGreaterThanOrEqual(68)
    expect(lefts[2] - lefts[1]).toBeGreaterThanOrEqual(68)
    const clamped = layoutChapters([{ x: 395, w: 60 }], 400)
    expect(clamped[0]).toBe(340)
    expect(labelsFit([{ x: 0, w: 60 }, { x: 0, w: 60 }], 128)).toBe(true)
    expect(labelsFit([{ x: 0, w: 60 }, { x: 0, w: 60 }], 127)).toBe(false)
  })
})

describe('slow near payout', () => {
  const base = { now: at('16:58'), running: true, speed: 6, slowWindow: WINDOW, enabled: true, memory: EMPTY }

  it('slows to 1 min/s inside the window and restores the speed after it', () => {
    const inside = slowDecision(base)
    expect(inside).toEqual({ play: 1, memory: { saved: 6, overridden: false } })
    expect(slowDecision({ ...base, now: at('17:02'), speed: 1, memory: inside.memory }).play).toBeNull()
    expect(slowDecision({ ...base, now: at('17:06'), speed: 1, memory: inside.memory })).toEqual({ play: 6, memory: EMPTY })
  })

  it('leaves the replay alone when off, paused, already slow or overridden', () => {
    expect(slowDecision({ ...base, enabled: false }).play).toBeNull()
    expect(slowDecision({ ...base, running: false }).play).toBeNull()
    expect(slowDecision({ ...base, speed: 1 }).play).toBeNull()
    expect(slowDecision({ ...base, memory: { saved: null, overridden: true } }).play).toBeNull()
    expect(slowDecision({ ...base, slowWindow: null }).play).toBeNull()
  })

  it('keeps the saved speed while paused after the window', () => {
    const memory = { saved: 6, overridden: false }
    expect(slowDecision({ ...base, now: at('17:10'), running: false, speed: 1, memory })).toEqual({ play: null, memory })
  })
})

describe('clock label and header helpers', () => {
  it('splits the SPEC clock label', () => {
    expect(clockParts('Mumbai · monsoon replay · 17:00 · simulated')).toEqual({ city: 'Mumbai', scenario: 'monsoon replay', time: '17:00', tail: 'simulated' })
    expect(clockParts('odd label')).toBeNull()
    expect(splitClockLabel('a · b · simulated')).toEqual({ main: 'a · b', tail: 'simulated' })
  })

  it('points the Merchant phone link at the scenario’s demo merchant (B5)', () => {
    expect(phoneMerchant({ clock: { ...CLOCK, scenario: 'buy_cover' }, demo_merchant_id: 'S-0142' })).toBe('S-0907')
    expect(phoneMerchant({ clock: { ...CLOCK, scenario: null }, demo_merchant_id: 'S-0300' })).toBe('S-0300')
    expect(phoneMerchant(null)).toBe('S-0142')
    expect(phoneMerchant({ clock: CLOCK, demo_merchant_id: 'S-0142' }, 'buy_cover')).toBe('S-0907')
  })

  it('names each live product once', () => {
    expect(liveBrands([status('sarvam_stt', 'LIVE'), status('sarvam_tts', 'LIVE'), status('whatsapp', 'LIVE'), status('kyc', 'SIMULATED')])).toEqual(['Sarvam', 'WhatsApp'])
    expect(MAX_LIVE_CHIPS).toBe(3)
  })
})

describe('Scrubber', () => {
  it('shows the chapters and seeks a minute before the one picked', () => {
    const onSeek = vi.fn<(hhmm: string) => void>()
    render(<Scrubber clock={CLOCK} busy={false} onSeek={onSeek} />)
    expect(screen.getByRole('progressbar', { name: /Replay at 16:00, 08:00 to 20:00/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /17:00 Trigger/ }))
    expect(onSeek).toHaveBeenCalledWith('16:59')
    expect(screen.getByRole('button', { name: /14:00 Alert/ }).dataset.passed).toBe('true')
    expect(screen.getByRole('button', { name: /17:04 Paid/ }).dataset.passed).toBe('false')
  })
})

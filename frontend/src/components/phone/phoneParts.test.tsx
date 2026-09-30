/** Merchant phone parts (SPEC §13.4 COVER_BLOCKED / COVER_LINK, §20 "Merchant phone", deck slides 1 and 7). */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Message } from '../../api/types'
import { ANIL } from '../../mock/fixtures'
import { testBackend } from '../../mock/testkit'
import { merchantDetailView } from '../../mock/views'
import { coverLink, coverOffer } from './coverOffer'
import { MerchantPanel, PRESENTER_STEPS } from './MerchantPanel'
import { BURST_MINUTES, burstScrollTop } from './useThreadScroll'
import { WAVE_BARS, waveHeights } from './Waveform'

const BLOCKED = "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert."
const LINK = 'To buy cover for later, pay ₹90 (₹3/day) here: https://paytm.me/sim-0A1B2C'
const out = (text_en: string): Pick<Message, 'direction' | 'text_en'> => ({ direction: 'OUTBOUND', text_en })
const MINUTE = 60_000

describe('waveform', () => {
  it('draws the same bars for the same note and different bars for another', () => {
    const a = waveHeights('M-1')
    expect(a).toHaveLength(WAVE_BARS)
    expect(waveHeights('M-1')).toEqual(a)
    expect(waveHeights('M-2')).not.toEqual(a)
    expect(Math.min(...a)).toBeGreaterThanOrEqual(4)
    expect(Math.max(...a)).toBeLessThanOrEqual(18)
  })
})

describe('cover offer', () => {
  it('reads the start date and the Paytm link from the catalogue lines', () => {
    expect(coverLink(out(LINK))).toEqual({ firstPayment: '₹90', perDay: '₹3', url: 'https://paytm.me/sim-0A1B2C' })
    expect(coverLink({ direction: 'INBOUND', text_en: LINK })).toBeNull()
    expect(coverOffer([out('Hello'), out(BLOCKED), out(LINK)])).toEqual({ startsOn: '25 August', link: { firstPayment: '₹90', perDay: '₹3', url: 'https://paytm.me/sim-0A1B2C' } })
    expect(coverOffer([out(BLOCKED)])).toEqual({ startsOn: '25 August', link: null })
    expect(coverOffer([out(LINK)])).toBeNull()
  })
})

describe('thread scroll', () => {
  it('scrolls to the start of the latest burst, or the bottom when it does not fit', () => {
    const t0 = Date.parse('2025-08-19T17:00:00+05:30')
    const rows = [
      { at: t0 - 60 * MINUTE, top: 0 },
      { at: t0, top: 300 },
      { at: t0 + (BURST_MINUTES - 1) * MINUTE, top: 420 },
    ]
    expect(burstScrollTop(rows, 400, 600)).toBe(292)
    expect(burstScrollTop(rows, 200, 600)).toBe(400)
    expect(burstScrollTop([{ at: t0, top: 40 }], 400, 300)).toBe(0)
    expect(burstScrollTop([], 400, 900)).toBe(900)
  })
})

describe('merchant panel', () => {
  it('shows the blocked cover card and folds the presenter notes behind a toggle', () => {
    const backend = testBackend()
    const anil = merchantDetailView(backend.runtime, ANIL)
    backend.dispose()
    render(
      <MemoryRouter>
        <MerchantPanel merchant={anil} scenario="buy_cover" offer={{ startsOn: '25 August', link: { firstPayment: '₹90', perDay: '₹3', url: 'https://paytm.me/sim-0A1B2C' } }} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('cover-blocked').textContent).toContain('cover starts 25 August')
    expect(screen.getByText('Paytm link sent for ₹90 (₹3 a day)')).toBeTruthy()
    expect(screen.queryByText(PRESENTER_STEPS.buy_cover[0])).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Presenter notes' }))
    expect(screen.getByText(PRESENTER_STEPS.buy_cover[0])).toBeTruthy()
  })

  it('opens the presenter notes from ?presenter=1', () => {
    const backend = testBackend()
    const anil = merchantDetailView(backend.runtime, ANIL)
    backend.dispose()
    render(
      <MemoryRouter initialEntries={['/merchant/S-0142?presenter=1']}>
        <MerchantPanel merchant={anil} scenario="monsoon" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('button', { name: 'Hide presenter notes' }).getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText(PRESENTER_STEPS.monsoon[1])).toBeTruthy()
  })
})

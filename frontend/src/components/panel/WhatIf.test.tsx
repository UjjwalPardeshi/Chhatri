/** The H24 what-if drawer (fs-08 11): the read-only line, debounce and abort, condition words, the example and reset. */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { WhatIfSide } from '../../api/opsWhatIf'
import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { clickWhatIf, offlineTiles, renderApp } from '../../test/renderApp'
import { exampleLine, resultLine, rulesLine, shownHours, withHour } from './whatIfModel'

const SIDE: WhatIfSide = { alert: 'NONE', alert_id: null, hourly_index_pct: [59, 58, null], window_index_pct: 59, shops_in_index: 62, already_triggered_today: false, fires: false, status: 'slow_day' }

describe('the words and the draft', () => {
  it('says would fire with the drop, or would not', () => {
    expect(resultLine({ ...SIDE, fires: true, drop_pct: 51 }, false)).toBe('Would fire: yes, 51% drop')
    expect(resultLine(SIDE, false)).toBe('Would not fire')
    expect(resultLine(SIDE, true)).toBe('Did not fire')
  })

  it("words the example with the engine's own arithmetic", () => {
    const example = { merchant_id: 'S-0142', shop_name: "Anil's Tea Stall", expected_day_paise: 438_000, drop_pct: 55, lost_paise: 240_900, share_paise: 120_500, cap_paise: 250_000, capped: false, amount_paise: 120_500, amount_label: '₹1,205', formula_en: '½ × ₹4,380 × 55% = ₹1,205', scope: 'amount arithmetic only' }
    expect(exampleLine(example)).toBe('Anil would be paid ₹1,205 (½ × ₹4,380 × 55%)')
    expect(exampleLine({ ...example, capped: true })).toBe('Anil would be paid ₹1,205 (½ × ₹4,380 × 55%, capped at ₹2,500)')
  })

  it('shows the fixed rule values as given', () => {
    expect(rulesLine({ index_floor_pct: 50, consecutive_hours: 3, min_shops_in_index: 20, lower_bound_pct: 90 })).toContain('every hour below 50% for 3 hours, at least 20 shops')
  })

  it('keeps all three hours when one is changed, and shows an empty hour as 0', () => {
    expect(shownHours({}, SIDE)).toEqual([59, 58, 0])
    expect(withHour({}, SIDE, 1, 49)).toEqual({ hourly_index_pct: [59, 49, 0] })
    expect(withHour({ alert: 'RAIN' }, SIDE, 0, 10)).toEqual({ alert: 'RAIN', hourly_index_pct: [10, 58, 0] })
  })
})

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  vi.stubEnv('VITE_FEATURES', 'h24_whatif')
  offlineTiles()
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

async function openDrawer() {
  const view = renderApp('/live', backend)
  await clickWhatIf()
  await screen.findByText(/^Evaluated at/)
  return view
}

const slider = (hour: number) => screen.getByRole('slider', { name: `Hour ${hour} sales as a percent of expected` })
const conditionRow = (name: RegExp) => screen.getByRole('row', { name })

describe('the what-if drawer', () => {
  it('is not offered while h24_whatif is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    renderApp('/live', backend)
    await screen.findByRole('button', { name: 'Play' })
    expect(screen.queryByRole('button', { name: 'What if…' })).toBeNull()
  })

  it('says read-only, when it was evaluated, and lists the five conditions for both sides', async () => {
    await openDrawer()
    expect(screen.getByText('Read-only: nothing is saved')).toBeTruthy()
    expect(screen.getByText('Evaluated at 08:00, window 05:00 to 08:00')).toBeTruthy()
    expect(screen.getAllByRole('row')).toHaveLength(6)
    expect(screen.getByRole('button', { name: 'Latest hour' })).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Back to what happened' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Rule: every hour below 50% for 3 hours/)).toBeTruthy()
  })

  it('waits 150 ms, sends one request for a burst of changes, and aborts the one in flight', async () => {
    const { api } = await openDrawer()
    const spy = vi.spyOn(api, 'whatIfArea')
    fireEvent.change(slider(1), { target: { value: '40' } })
    fireEvent.change(slider(1), { target: { value: '41' } })
    fireEvent.change(slider(1), { target: { value: '42' } })
    expect(spy).not.toHaveBeenCalled()
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy.mock.calls[0][0]).toMatchObject({ zone_id: 'Z7', overrides: { hourly_index_pct: [42, expect.any(Number), expect.any(Number)] } })
    expect(spy.mock.calls[0][0].at).toBe('2025-08-19T08:00:00+05:30')
    const first = spy.mock.calls[0][1] as AbortSignal
    fireEvent.change(slider(2), { target: { value: '30' } })
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    expect(first.aborted).toBe(true)
    await act(() => new Promise((resolve) => setTimeout(resolve, 300)))
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('pins the hour when it opens and repins on Latest hour', async () => {
    const { api } = await openDrawer()
    const spy = vi.spyOn(api, 'whatIfArea')
    await act(() => api.seek('10:00'))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Already triggered today' }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy.mock.calls[0][0].at).toBe('2025-08-19T08:00:00+05:30')
    fireEvent.click(screen.getByRole('button', { name: 'Latest hour' }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    expect(spy.mock.calls[1][0].at).toBeUndefined()
    await screen.findByText('Evaluated at 10:00, window 07:00 to 10:00')
  })

  it('words each condition and the verdict, and prices the example shop', async () => {
    await openDrawer()
    fireEvent.click(screen.getByRole('button', { name: 'Heat' }))
    await waitFor(() => expect(within(conditionRow(/A rain or civic alert covers/)).getByText(/a heat alert, which the rule ignores/)).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Rain' }))
    for (const hour of [1, 2, 3]) fireEvent.change(slider(hour), { target: { value: '40' } })
    await screen.findByText(/^Would fire: yes, \d+% drop$/)
    expect(within(conditionRow(/Every hour is below 50%/)).getAllByLabelText('Met')).toHaveLength(1)
    expect(within(conditionRow(/Every hour is below 50%/)).getByText(/40, 40, 40/)).toBeTruthy()
    expect(await screen.findByText(/^Anil would be paid ₹[\d,]+ \(½ × ₹4,380 × \d+%\)\./)).toBeTruthy()
  })

  it('goes back to what happened', async () => {
    await openDrawer()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Already triggered today' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Back to what happened' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Back to what happened' }))
    await waitFor(() => expect((screen.getByRole('checkbox', { name: 'Already triggered today' }) as HTMLInputElement).checked).toBe(false))
    expect((screen.getByRole('button', { name: 'Back to what happened' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('closes with Esc and with Close', async () => {
    await openDrawer()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Read-only: nothing is saved')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'What if…' }))
    await screen.findByText('Read-only: nothing is saved')
    fireEvent.click(screen.getByRole('button', { name: 'Close what if' }))
    expect(screen.queryByText('Read-only: nothing is saved')).toBeNull()
  })

  it('says plainly when there is no completed window yet, and offers Retry on other errors', async () => {
    const { api } = renderApp('/live', backend)
    await screen.findByRole('region', { name: 'Zone Z7' })
    vi.spyOn(api, 'whatIfArea').mockRejectedValueOnce(new ApiError('conflict', 'no completed 3-hour window yet', 409))
    await clickWhatIf()
    expect((await screen.findByRole('alert')).textContent).toContain('No completed 3-hour window yet')
    fireEvent.click(screen.getByRole('button', { name: 'Close what if' }))
    vi.spyOn(api, 'whatIfArea').mockRejectedValueOnce(new ApiError('internal', 'boom', 500))
    fireEvent.click(screen.getByRole('button', { name: 'What if…' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Cannot compute')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await screen.findByText(/^Evaluated at/)
  })
})

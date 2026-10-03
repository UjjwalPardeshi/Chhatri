/** Header and replay controls (SPEC §17.1, §20 header) against the mock. */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { offlineTiles, renderApp } from '../../test/renderApp'
import { progressPct, splitClockLabel } from './ControlBar'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  offlineTiles()
  backend = testBackend()
})
afterEach(() => backend.dispose())

const clockText = () => document.querySelector('.clock-label')?.textContent ?? ''

describe('control bar', () => {
  it('splits the clock label and computes progress', () => {
    expect(splitClockLabel('Mumbai · monsoon replay · 17:00 · simulated')).toEqual({ main: 'Mumbai · monsoon replay · 17:00', tail: 'simulated' })
    expect(splitClockLabel('plain')).toEqual({ main: 'plain', tail: '' })
    const clock = { scenario: 'monsoon' as const, scenario_title: 'Monsoon replay', now: '2025-08-19T12:00:00+05:30', start: '2025-08-19T08:00:00+05:30', end: '2025-08-19T16:00:00+05:30', running: false, speed: 6, label: '' }
    expect(progressPct(clock)).toBe(50)
    expect(progressPct({ ...clock, end: clock.start })).toBe(0)
  })

  it('steps, seeks, validates, plays, pauses, resets and switches scenarios', async () => {
    renderApp('/merchant/S-0142', backend)
    await waitFor(() => expect(clockText()).toContain('08:00'))
    fireEvent.click(screen.getByRole('button', { name: '+1 h' }))
    await waitFor(() => expect(clockText()).toContain('09:00'))
    const seek = screen.getByRole('textbox', { name: 'Seek to time (HH:MM)' })
    fireEvent.change(seek, { target: { value: '9am' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    expect(seek.getAttribute('aria-invalid')).toBe('true')
    fireEvent.change(seek, { target: { value: '17:05' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    await waitFor(() => expect(clockText()).toContain('17:05'))
    fireEvent.change(seek, { target: { value: '23:59' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Pick a time between 08:00 and 20:00.')
    expect(screen.queryByText(/validation_error/i)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    await screen.findByRole('button', { name: 'Pause' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Speed' }), { target: { value: '120' } })
    await waitFor(() => expect(backend.clock.speed).toBe(120))
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    await screen.findByRole('button', { name: 'Play' })
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    await waitFor(() => expect(clockText()).toContain('08:00'))
    fireEvent.change(screen.getByRole('combobox', { name: 'Scenario' }), { target: { value: 'buy_cover' } })
    await waitFor(() => expect(clockText()).toContain('buy cover replay'))
    expect(await screen.findByText('Ramesh Vada Pav', { exact: false })).toBeTruthy()
  })
})

describe('control bar on a phone', () => {
  it('closes the "More" popover after a seek, so the page is visible again', async () => {
    renderApp('/live', backend)
    await waitFor(() => expect(clockText()).toContain('08:00'))
    const more = screen.getByRole('button', { name: 'More replay controls' })
    fireEvent.click(more)
    expect(more.getAttribute('aria-expanded')).toBe('true')
    fireEvent.change(screen.getByRole('textbox', { name: 'Seek to time (HH:MM)' }), { target: { value: '17:05' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    await waitFor(() => expect(clockText()).toContain('17:05'))
    expect(more.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(more)
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    await waitFor(() => expect(clockText()).toContain('08:00'))
    expect(more.getAttribute('aria-expanded')).toBe('false')
  })
})

describe('header', () => {
  it('shows integration badges, the sound toggle and the open case count', async () => {
    backend.seek('17:05')
    renderApp('/policy', backend)
    const summary = await screen.findByRole('button', { name: /live · .* simulated/ })
    fireEvent.click(summary)
    const items = document.querySelectorAll('[data-mode="SIMULATED"]')
    expect(items.length).toBeGreaterThan(5)
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(summary.getAttribute('aria-expanded')).toBe('false'))
    fireEvent.click(summary)
    fireEvent.mouseDown(document.body)
    await waitFor(() => expect(summary.getAttribute('aria-expanded')).toBe('false'))
    const sound = screen.getByRole('button', { name: /Enable sound/ })
    fireEvent.click(sound)
    expect(sound.textContent).toContain('Sound on')
    fireEvent.click(sound)
    expect(sound.textContent).toContain('Enable sound')
    backend.step(1)
    const { api } = await import('../../mock/testkit').then((m) => m.testApi(backend))
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    await waitFor(() => expect(document.querySelector('.app-nav__count')?.textContent).toBe('1'))
  })

  it('x6_provider_panel: a forced lender shows the FALLBACK segment and the "forced" chip (fs-08 section 20)', async () => {
    vi.stubEnv('VITE_FEATURES', 'x6_provider_panel')
    backend.runtime.lenderForced = true
    renderApp('/policy', backend)
    const summary = await screen.findByRole('button', { name: /live · .* simulated · 1 fallback · forced/ })
    expect(summary.querySelector('.integrations-summary__seg--fallback')?.textContent).toContain('1 fallback')
    expect(summary.querySelector('.integrations-summary__seg--forced')?.textContent).toBe('forced')
    fireEvent.click(summary)
    const kyc = document.querySelector('[data-name="kyc"] button') as HTMLButtonElement
    expect(kyc.disabled).toBe(true)
    vi.unstubAllEnvs()
  })

  it('shows the reconnecting pill during an outage', async () => {
    renderApp('/policy', backend)
    await screen.findByRole('heading', { name: /Automatic when the data is clear/ })
    await waitFor(() => expect(document.querySelector('.connection-pill')).toBeNull())
    backend.outage(60_000)
    const pill = await screen.findByText('Reconnecting…')
    expect(pill.closest('[data-state]')?.getAttribute('data-state')).toBe('reconnecting')
  })
})

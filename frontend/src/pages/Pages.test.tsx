/** Audit, Backtest, Policy and not-found pages against the mock (SPEC §11, §16, §20). */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testBackend } from '../mock/testkit'
import { renderApp } from '../test/renderApp'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  backend = testBackend()
})
afterEach(() => backend.dispose())

describe('Audit page', () => {
  it('lists entries, filters them and verifies the chain', async () => {
    backend.seek('17:05')
    renderApp('/audit', backend)
    expect(await screen.findByRole('heading', { name: 'Audit log' })).toBeTruthy()
    await waitFor(() => expect(document.querySelectorAll('.audit-table tbody tr.audit-row').length).toBeGreaterThan(10))
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter audit entries' }), { target: { value: 'payout' } })
    const rows = [...document.querySelectorAll('.audit-table tbody tr.audit-row')]
    expect(rows.every((r) => /payout/i.test(r.textContent ?? ''))).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Verify chain' }))
    expect(await screen.findByText(/Chain valid ·/)).toBeTruthy()
    const entries = backend.runtime.audit
    entries[1] = { ...entries[1], actor: 'mallory' }
    fireEvent.click(screen.getByRole('button', { name: 'Verify chain' }))
    expect(await screen.findByText(/Chain INVALID · first bad entry #2/)).toBeTruthy()
  })

  it('shows an error when the backend is down', async () => {
    backend.outage(60_000)
    renderApp('/audit', backend)
    expect(await screen.findByText('Could not load the audit log')).toBeTruthy()
  })
})

describe('Backtest and Policy', () => {
  it('shows the backtest label and metrics', async () => {
    renderApp('/backtest', backend)
    expect(await screen.findByRole('heading', { name: 'Would Chhatri have paid the real losses?' })).toBeTruthy()
    expect((await screen.findAllByText(/simulated sales · real Open-Meteo rainfall/)).length).toBeGreaterThan(0)
  })

  it('shows the policy with the live tests', async () => {
    renderApp('/policy', backend)
    expect(await screen.findByRole('heading', { name: /Automatic when the data is clear/ })).toBeTruthy()
    expect(await screen.findByText('Three live tests in our demo')).toBeTruthy()
  })

  it('renders not found for unknown routes', async () => {
    renderApp('/nowhere', backend)
    expect(await screen.findByText('Page not found')).toBeTruthy()
  })
})

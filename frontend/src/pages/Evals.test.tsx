/** The /evals page (H25): the flag, the no-run state with no number, the banner, the six suites, a measured run with its k of n, and the error state. */
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import type { EvalsSummary } from '../api/evals'
import type { MockBackend } from '../mock/backend'
import { testApi, testBackend } from '../mock/testkit'
import { AppRoutes } from '../App'
import { AppShell } from '../components/layout/AppShell'
import { LiveProvider } from '../state/live'
import { renderApp } from '../test/renderApp'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  vi.stubEnv('VITE_FEATURES', 'h25_evals')
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

const MEASURED: EvalsSummary = {
  measured: true,
  run: { run_id: 'run-7', commit: 'abc1234', started_at: '2026-10-02T10:00:00+05:30', ended_at: '2026-10-02T10:20:00+05:30', data_origin: 'synthetic', held_out_sha256: ['00'], providers: [{ component: 'slips', mode: 'FALLBACK', provider: 'sarvam', model: 'sarvam-vision' }] },
  suites: ['intent', 'guard', 'ask', 'slips', 'voice', 'chain'].map((id) =>
    id === 'slips'
      ? {
          id: 'slips' as const, status: 'MEASURED' as const, reason: null,
          metrics: [{ id: 'slips.wrong_read_passes_gate', suite: 'slips' as const, title: 'Wrong reads that pass the gate', k: 0, n: 120, value: 0, interval: { method: 'wilson', level: 0.95, low: 0, high: 0.031 }, direction: 'at_most' as const, target: 0, target_source: 'proposed', meets_target: true, interval_clears_target: false, status: 'MET, WIDE INTERVAL' as const, reason: null, p50_ms: null, p95_ms: null, within_target_share: null }],
        }
      : { id: id as 'intent', status: 'NOT_MEASURED' as const, reason: 'no key', metrics: [] },
  ),
}

/** The console against the mock backend, with the evaluation call replaced (a stored run, or a broken body). */
function renderWith(evalsSummary: () => Promise<EvalsSummary>) {
  const kit = testApi(backend)
  render(
    <MemoryRouter initialEntries={['/evals']}>
      <LiveProvider api={{ ...kit.api, evalsSummary }} mock>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LiveProvider>
    </MemoryRouter>,
  )
}

describe('the /evals page', () => {
  it('does not exist while h25_evals is off, and has no header link', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    renderApp('/evals', backend)
    expect(await screen.findByText('Page not found')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Evals' })).toBeNull()
  })

  it('has a header link with the flag', async () => {
    renderApp('/evals', backend)
    expect(await screen.findByRole('heading', { name: 'AI evaluation' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Evals' })).toBeTruthy()
  })

  it('says NOT MEASURED in all six suites with no number, the banner, and "Run: none stored"', async () => {
    renderApp('/evals', backend)
    await waitFor(() => expect(screen.getByTestId('eval-run').textContent).toBe('Run: none stored'))
    expect(screen.getByTestId('eval-banner').textContent).toContain('Synthetic data only. Results on generated slips and written questions say little about real merchants or real hospital paper.')
    for (const [id, title] of [['intent', 'S1 Intent routing'], ['guard', 'S2 Guard red-team'], ['ask', 'S3 Ask end to end'], ['slips', 'S4 Slip reading and the gate'], ['voice', 'S5 Voice'], ['chain', 'S6 Chains and labels']]) {
      const card = screen.getByTestId(`eval-suite-${id}`)
      expect(within(card).getByRole('heading', { name: title })).toBeTruthy()
      expect(card.textContent).toContain('NOT MEASURED')
      expect(card.textContent).toContain('no run stored')
      expect(card.textContent).not.toMatch(/\d+ of \d+|%/)
    }
    expect(document.querySelectorAll('[data-testid="eval-metric"]')).toHaveLength(0)
    expect(screen.getByTestId('eval-none').textContent).toContain('no number is shown')
  })

  it('shows a measured run: the header, the provider chip with its mode, k of n, the interval, the target and the status chip', async () => {
    renderWith(() => Promise.resolve(MEASURED))
    const header = await screen.findByTestId('eval-run')
    expect(header.textContent).toContain('Run run-7')
    expect(header.textContent).toContain('data origin: synthetic')
    expect(within(screen.getByTestId('eval-provider')).getByText(/FALLBACK/).getAttribute('data-mode')).toBe('FALLBACK')
    const metric = screen.getByTestId('eval-metric')
    expect(screen.getByTestId('eval-value').textContent).toBe('0 of 120, below the upper bound with 95% confidence')
    expect(metric.textContent).toContain('interval 0.0% to 3.1% (95%, wilson)')
    expect(metric.textContent).toContain('target 0 (proposed)')
    expect(within(metric).getByText(/MET, WIDE INTERVAL/).getAttribute('data-status')).toBe('MET, WIDE INTERVAL')
    expect(screen.getByTestId('eval-suite-intent').textContent).toContain('no key')
    expect(screen.queryByTestId('eval-none')).toBeNull()
  })

  it('shows the error state with a retry when the result breaks the contract', async () => {
    renderWith(() => Promise.reject(new ApiError('contract_violation', 'evals: expected an object', 0)))
    expect(await screen.findAllByText('Could not load this')).toBeTruthy()
  })
})

/** X6 provider panel and H26 labels (card 4.5, fs-08 sections 9.1, 9.5, 9.7) against the mock. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CaseEvidence, IntegrationStatus, Message, SlipEvidence } from '../../api/types'
import { reasonWords } from '../../lib/providerLabels'
import type { MockBackend } from '../../mock/backend'
import { integrationRows } from '../../mock/fixtures'
import { testApi, testBackend } from '../../mock/testkit'
import { offlineTiles, renderApp } from '../../test/renderApp'
import { Evidence } from '../claims/Evidence'
import { LiveProvider } from '../../state/live'
import { MessageBubble } from '../phone/Bubbles'
import { integrationCounts } from './IntegrationBadges'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  offlineTiles()
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

const slip = (extra: Partial<SlipEvidence>): CaseEvidence => ({
  slip: { media_url: '/s.png', patient_name: 'Anil', admission_date: null, discharge_date: null, hospital_name: null, document_type: 'admission_slip', confidence: 0.92, source: 'simulated', ...extra },
  kyc_name: 'ANIL',
})

const message = (meta: Message['meta']): Message => ({
  id: 'M-1', merchant_id: 'S-0142', direction: 'OUTBOUND', channel: 'SIMULATOR', kind: 'TEXT',
  text_hi: null, text_en: 'Here is the answer', audio_url: null, media_url: null, card: null,
  created_at: '2025-08-19T12:00:00+05:30', meta,
})

const summary = () => screen.findByRole('button', { name: /live · .* simulated/ })

describe('mock parity (fs-08 9.7)', () => {
  it('serves 17 rows, all simulated, with the extended fields; only the lender switches', () => {
    const rows = integrationRows(false)
    expect(rows).toHaveLength(17)
    expect(rows.map((r) => r.name)).toEqual(expect.arrayContaining(['gemini_chat', 'gemini_vision']))
    expect(rows.every((r) => r.mode === 'SIMULATED' && !r.forced)).toBe(true)
    expect(rows.filter((r) => r.switchable).map((r) => r.name)).toEqual(['lender'])
    const forced = integrationRows(true).find((r) => r.name === 'lender')
    expect(forced).toMatchObject({ mode: 'FALLBACK', fallback_reason: 'FORCED', forced: true, switchable: true })
  })

  it('counts the three modes', () => {
    const rows: IntegrationStatus[] = [
      { name: 'kyc', mode: 'LIVE', detail: '' },
      { name: 'lender', mode: 'FALLBACK', detail: '' },
      { name: 'memory', mode: 'SIMULATED', detail: '' },
    ]
    expect(integrationCounts(rows)).toEqual({ live: 1, simulated: 1, fallback: 1 })
  })

  it('answers the switch route like the real one: flag, token, unknown, 409, 422', async () => {
    const { api } = await import('../../mock/testkit').then((m) => m.testApi(backend))
    await expect(api.setFallback('lender', true)).rejects.toMatchObject({ code: 'NO_OFFICER_TOKEN' })
    api.client.setOfficerToken((await api.session()).officer_token)
    await expect(api.setFallback('lender', true)).rejects.toMatchObject({ status: 404 })
    vi.stubEnv('VITE_FEATURES', 'x6_provider_panel')
    await expect(api.setFallback('nope', true)).rejects.toMatchObject({ status: 404 })
    await expect(api.setFallback('kyc', true)).rejects.toMatchObject({ status: 409 })
    const row = await api.setFallback('lender', true)
    expect(row).toMatchObject({ mode: 'FALLBACK', forced: true })
    expect((await api.integrations()).find((r) => r.name === 'lender')?.forced).toBe(true)
    backend.load('illness')
    expect(backend.runtime.lenderForced).toBe(true)
    expect(await api.setFallback('lender', false)).toMatchObject({ mode: 'SIMULATED', forced: false })
  })
})

describe('header chip and panel', () => {
  it('flag off: no switches, no forced chip, no footer', async () => {
    backend.runtime.lenderForced = true
    renderApp('/policy', backend)
    fireEvent.click(await summary())
    expect(screen.queryByRole('button', { name: /Force fallback/ })).toBeNull()
    expect(document.querySelector('.integrations-summary__seg--forced')).toBeNull()
    expect(document.querySelector('.provider-flags')).toBeNull()
    expect(document.querySelector('.integration--fallback')).not.toBeNull()
  })

  it('flag on: forcing the lender turns the chip orange, shows "forced", and Clear all releases it', async () => {
    vi.stubEnv('VITE_FEATURES', 'x6_provider_panel,x4_lender_request')
    renderApp('/policy', backend)
    const chip = await summary()
    expect(document.querySelector('.integrations-summary__seg--fallback')).toBeNull()
    fireEvent.click(chip)
    const panel = await screen.findByRole('region', { name: 'Integrations' })
    expect(within(panel).getByText('Flags on: x4_lender_request, x6_provider_panel')).toBeTruthy()
    const kyc = panel.querySelector('[data-name="kyc"]') as HTMLElement
    expect(within(kyc).getByRole('button', { name: /Force fallback: KYC/ }).hasAttribute('disabled')).toBe(true)
    expect(within(kyc).getByText('static demo: nothing live to force')).toBeTruthy()
    const chat = panel.querySelector('[data-name="sarvam_chat"]') as HTMLElement
    expect(within(chat).getByText('static demo: nothing live to force')).toBeTruthy()
    expect(within(chat).getByText('mock')).toBeTruthy()
    fireEvent.click(within(panel).getByRole('button', { name: 'Force fallback: Lender' }))
    await waitFor(() => expect(document.querySelector('.integrations-summary__seg--forced')?.textContent).toBe('forced'))
    expect(document.querySelector('.integrations-summary__seg--fallback')?.textContent).toContain('1')
    expect(chip.getAttribute('aria-label')).toContain('1 fallback')
    const lender = panel.querySelector('[data-name="lender"]') as HTMLElement
    expect(lender.getAttribute('data-mode')).toBe('FALLBACK')
    expect(within(lender).getByText('forced for the demo')).toBeTruthy()
    expect(backend.runtime.lenderForced).toBe(true)
    fireEvent.click(within(panel).getByRole('button', { name: 'Clear all' }))
    await waitFor(() => expect(document.querySelector('.integrations-summary__seg--forced')).toBeNull())
    expect(backend.runtime.lenderForced).toBe(false)
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
  })
})

describe('H26 labels', () => {
  it('turns reason codes into words and keeps unknown ones visible', () => {
    expect(reasonWords('FORCED')).toBe('forced for the demo')
    expect(reasonWords('TIMEOUT')).toBe('the provider timed out')
    expect(reasonWords('WEIRD')).toBe('WEIRD')
    expect(reasonWords(null)).toBeNull()
  })

  it('puts the slip reader mode next to Read confidence; unchanged without a label', () => {
    const { unmount } = render(<Evidence evidence={slip({})} />, { wrapper: LiveStub })
    expect(screen.getByText('92% (simulated)')).toBeTruthy()
    expect(screen.queryByText('Slip reader')).toBeNull()
    unmount()
    render(<Evidence evidence={slip({ mode: 'FALLBACK', provider: 'simulated', model: null, fallback_reason: 'FORCED' })} />, { wrapper: LiveStub })
    expect(screen.getByText('92% (simulated)')).toBeTruthy()
    expect(screen.getByText('Slip reader')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'details' }))
    expect(screen.getByText('simulated · forced for the demo')).toBeTruthy()
  })

  it('shows the mode word on a model-path bubble, details behind a tap, nothing on an engine bubble', () => {
    const { rerender } = render(
      <MessageBubble message={message({ mode: 'FALLBACK', provider: 'template', model: null, fallback_reason: 'TIMEOUT' })} />,
      { wrapper: LiveStub },
    )
    expect(screen.getByText('FALLBACK', { exact: false })).toBeTruthy()
    expect(screen.queryByText('template · the provider timed out')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'details' }))
    expect(screen.getByText('template · the provider timed out')).toBeTruthy()
    rerender(<MessageBubble message={message({})} />)
    expect(document.querySelector('.mode-chip')).toBeNull()
  })
})

function LiveStub({ children }: { children: ReactNode }) {
  const { api } = testApi(backend)
  return (
    <MemoryRouter>
      <LiveProvider api={api} mock>
        {children}
      </LiveProvider>
    </MemoryRouter>
  )
}

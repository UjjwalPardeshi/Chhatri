/** Claims officer flow against the mock (SPEC §12, §20 "Claims"). */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testApi, testBackend } from '../mock/testkit'
import { renderApp } from '../test/renderApp'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  backend = testBackend()
})
afterEach(() => backend.dispose())

async function referMismatch(): Promise<void> {
  const { api } = testApi(backend)
  await api.load('illness_mismatch')
  await api.seek('11:20')
  await api.sendVoiceDemo('S-0142', 'ill')
  await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
}

describe('Claims', () => {
  it('shows an empty queue with guidance', async () => {
    renderApp('/claims', backend)
    expect(await screen.findByText('No case selected')).toBeTruthy()
  })

  it('has one h1, the queue heading', async () => {
    renderApp('/claims', backend)
    await screen.findByText('No case selected')
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Claims queue'])
  })

  it('approves a referred mismatch claim and shows the officer decision inline', async () => {
    await referMismatch()
    renderApp('/claims', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    expect(within(detail).getByText('REFERRED')).toBeTruthy()
    expect(within(detail).getByText(/Why a human:/)).toBeTruthy()
    fireEvent.change(within(detail).getByRole('textbox', { name: 'Officer note' }), { target: { value: 'Hospital confirmed by phone' } })
    const approve = within(detail).getByRole('button', { name: 'Approve' })
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(approve)
    expect(await screen.findByText('Officer decision')).toBeTruthy()
    expect(await screen.findByText(/Hospital confirmed by phone/)).toBeTruthy()
    expect(await screen.findByText('Policy engine decision')).toBeTruthy()
    expect(screen.getByText(/^Personal claim ₹1,500 for Anil.s Tea Stall sent to a human: the name on the slip/)).toBeTruthy()
    expect(await screen.findByText(/₹1,500 credited to Anil.s Tea Stall at 11:24, with the settlement\./)).toBeTruthy()
    await waitFor(() => expect(backend.runtime.payouts.at(-1)?.status).toBe('CREDITED'))
    expect(screen.getByRole('link', { name: 'Open the phone' }).getAttribute('href')).toBe('/merchant/S-0142')
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => expect(screen.queryByText('No case selected')).toBeTruthy())
  })

  it('opens the slip large to compare names and closes it with Escape', async () => {
    await referMismatch()
    renderApp('/claims', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    expect(within(detail).getByText('Name on the slip doesn’t match KYC')).toBeTruthy()
    fireEvent.click(within(detail).getByRole('button', { name: 'Open the slip large' }))
    const dialog = within(screen.getByRole('dialog', { name: 'Hospital slip' }))
    expect(dialog.getByText('Sunil Pawar')).toBeTruthy()
    expect(dialog.getByText(/Match score 41 \/ 100/)).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('reads the receipt: a Source column of chips with the origin word and the counterfactual note', async () => {
    await referMismatch()
    renderApp('/claims', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    expect(await within(detail).findByRole('columnheader', { name: 'Source' })).toBeTruthy()
    const chips = await waitFor(() => {
      const found = detail.querySelectorAll('.source-chip')
      expect(found.length).toBeGreaterThan(0)
      return [...found]
    })
    expect(chips.every((c) => /SIMULATED|CONFIG|LIVE/.test(c.textContent ?? ''))).toBe(true)
    expect(detail.textContent?.toLowerCase()).not.toContain('verified by')
  })

  it('drops a case link from another run instead of showing an error', async () => {
    await referMismatch()
    renderApp('/claims?case=C-9999', backend)
    expect(await screen.findByRole('article', { name: 'Case C-2291' })).toBeTruthy()
    expect(screen.queryByText(/not_found/)).toBeNull()
  })

  it('declines a dispute from a deep link', async () => {
    const { api } = testApi(backend)
    await api.seek('17:05')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    renderApp('/claims?case=C-2291', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    expect(within(detail).getByText('Dispute')).toBeTruthy()
    const decline = within(detail).getByRole('button', { name: 'Reject dispute' })
    await waitFor(() => expect((decline as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(decline)
    expect(await screen.findByText(/Dispute declined by a claims officer/)).toBeTruthy()
  })

  it('shows an inline error when the decision fails', async () => {
    await referMismatch()
    renderApp('/claims', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    const approve = within(detail).getByRole('button', { name: 'Approve' })
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false))
    const { api } = testApi(backend)
    await api.client.post('/api/cases/C-2291/approve', { note: '' }, false).catch(() => undefined)
    backend.runtime.cases = backend.runtime.cases.map((c) => ({ ...c, status: 'DECLINED' as const }))
    fireEvent.click(approve)
    expect(await screen.findByText(/\[conflict\]/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
  })
})

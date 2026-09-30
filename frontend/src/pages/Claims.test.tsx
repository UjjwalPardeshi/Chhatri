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
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => expect(screen.queryByText('No case selected')).toBeTruthy())
  })

  it('declines a dispute from a deep link', async () => {
    const { api } = testApi(backend)
    await api.seek('17:05')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    renderApp('/claims?case=C-2291', backend)
    const detail = await screen.findByRole('article', { name: 'Case C-2291' })
    expect(within(detail).getByText('Dispute')).toBeTruthy()
    const decline = within(detail).getByRole('button', { name: 'Decline' })
    await waitFor(() => expect((decline as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(decline)
    expect(await screen.findByText(/Declined by the claims officer/)).toBeTruthy()
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
    expect(await screen.findByText(/\[CONFLICT\]/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
  })
})

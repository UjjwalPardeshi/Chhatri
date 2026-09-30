/** Merchant phone against the mock (SPEC §13, §20 "Merchant phone", deck slides 1 and 7). */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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

describe('Merchant phone', () => {
  it('shows the monsoon payout card, answers "why" by voice and opens a dispute case', async () => {
    backend.seek('17:05')
    renderApp('/merchant/S-0142', backend)
    expect(await screen.findByText('Paytm · Chhatri')).toBeTruthy()
    expect(screen.getByText('Merchant protection · Hindi, English')).toBeTruthy()
    expect(await screen.findByText('No claim needed')).toBeTruthy()
    expect(document.querySelector('.payout-card__amount')?.textContent).toBe('₹1,380')
    fireEvent.click(await screen.findByRole('button', { name: /मुझे इतने ही पैसे क्यों मिले/ }))
    expect(await screen.findByText(/^Your usual Tuesday/)).toBeTruthy()
    expect(screen.getAllByText('browser voice · simulated').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /मेरा नुकसान ज़्यादा हुआ/ }))
    const chip = await screen.findByRole('link', { name: /C-2291/ })
    expect(chip.getAttribute('href')).toBe('/claims?case=C-2291')
    expect(screen.getByText('₹4,380')).toBeTruthy()
  })

  it('sends typed text and a sample slip in the illness flow', async () => {
    backend.load('illness')
    backend.seek('11:20')
    renderApp('/merchant/S-0142', backend)
    const input = await screen.findByRole('textbox', { name: 'Message' })
    fireEvent.change(input, { target: { value: 'hello' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Message' }) as HTMLInputElement).value).toBe(''))
    fireEvent.click(screen.getByRole('button', { name: /मैं अस्पताल में हूँ/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Send a photo' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: /Anil's admission slip/ }))
    await waitFor(() => expect(document.querySelector('[data-kind="IMAGE"]')).toBeTruthy())
  })

  it('rejects an invalid merchant id and reports unknown merchants', async () => {
    renderApp('/merchant/bogus', backend)
    expect(await screen.findByText('Unknown merchant')).toBeTruthy()
  })

  it('shows an error state for a merchant the backend does not know', async () => {
    renderApp('/merchant/S-0001', backend)
    expect(await screen.findByText('Could not load the merchant')).toBeTruthy()
    expect(await screen.findByText('Could not load the conversation')).toBeTruthy()
  })

  it('shows a blocked cover quote with the Paytm link for Ramesh', async () => {
    backend.load('buy_cover')
    renderApp('/merchant/S-0907', backend)
    fireEvent.click(await screen.findByRole('button', { name: 'Red alert tomorrow. Cover me today.' }))
    const links = await screen.findAllByRole('link', { name: /paytm\.me\/sim-/ })
    expect(links[0].getAttribute('href')).toMatch(/^https:\/\/paytm\.me\/sim-[0-9A-F]{6}$/)
    expect(screen.getAllByText(/^New cover starts after the waiting period/)).toHaveLength(2)
    const blocked = within(screen.getByTestId('cover-blocked'))
    expect(blocked.getByText('Blocked')).toBeTruthy()
    expect(blocked.getByText(/^Paytm link sent for ₹[\d,.]+ \(₹[\d,.]+ a day\)$/)).toBeTruthy()
  })
})

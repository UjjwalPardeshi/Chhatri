/** S4 Claims (fs-04 section 8): one list of everything Chhatri is doing or has done for the merchant's money (AC-18, AC-22). */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { claim, disputeClosed, disputeOpen, personalReferred, personalWaitingForSlip } from '../../test/claimFixtures'
import { session, stubClaims } from '../../test/claimScenes'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

const text = (id: string) => screen.getByTestId(id).textContent ?? ''

async function openClaims(kit: { backend: MockBackend }, search = '?lang=en&screen=claims', state = 'ready') {
  backend = kit.backend
  const view = renderStandalone(`/merchant/S-0142/app${search}`, kit.backend)
  await waitFor(() => expect(screen.getByTestId('screen-claims').getAttribute('data-state')).toBe(state))
  return view
}

describe('Claims on a paid day', () => {
  it("lists Anil's claim as a card: kind, day, status, amount and what happens next", async () => {
    await openClaims(await session('monsoon', '17:05'))
    const card = screen.getByTestId('claim-card-CL-000142')
    expect(within(screen.getByTestId('claims-list')).getAllByRole('listitem')).toHaveLength(1)
    expect(card.textContent).toContain('Rain and lost sales')
    expect(card.textContent).toContain('19 August')
    expect(card.textContent).toContain('Paid')
    expect(card.textContent).toContain('₹1,380')
    expect(card.textContent).toContain('All steps are done. Your receipt is ready.')
    expect(card.getAttribute('data-status')).toBe('APPROVED')
    expect(within(card).getByRole('link').getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142')
  })

  it('opens the claim from the card and says open_latest next', async () => {
    await openClaims(await session('monsoon', '17:05'))
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('open_latest')
    fireEvent.click(within(screen.getByTestId('claim-card-CL-000142')).getByRole('link'))
    await screen.findByTestId('screen-claim')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142')
  })

  it('speaks Hindi by default, with the amount in digits', async () => {
    await openClaims(await session('monsoon', '17:05'), '?screen=claims')
    const card = screen.getByTestId('claim-card-CL-000142')
    expect(card.textContent).toContain('बारिश से बिक्री का नुकसान')
    expect(card.textContent).toContain('भुगतान हुआ')
    expect(card.textContent).toContain('₹1,380')
  })

  it('has one heading level under the app bar title and no heading for the list itself', async () => {
    await openClaims(await session('monsoon', '17:05'))
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(within(screen.getByTestId('claim-card-CL-000142')).getByRole('heading').tagName).toBe('H2')
  })
})

describe('Claims with nothing yet', () => {
  it('says there are no claims and offers what is covered', async () => {
    await openClaims(await session('monsoon', '16:59'), '?lang=en&screen=claims', 'empty')
    expect(text('claims-empty')).toContain('No claims yet')
    expect(screen.queryByTestId('claims-list')).toBeNull()
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_coverage_empty')
  })
})

describe('Claims when the data is wrong (AC-18)', () => {
  it('shows contract_violation for an AREA item that is REFERRED, and draws no card', async () => {
    stubClaims([claim({ outcome: 'REFERRED', case_id: 'C-2291', case_status: 'OPEN', due_by: '2025-08-20T17:12:00+05:30' })])
    await openClaims(await session('monsoon', '17:05'), '?lang=en&screen=claims', 'error')
    expect(text('app-error')).toContain('Error code: contract_violation')
    expect(screen.queryByTestId('claims-list')).toBeNull()
    expect(screen.queryByTestId('app-nba')).toBeNull()
  })

  it('shows the error state with the code, and Retry asks the API again', async () => {
    const real = ApiClient.prototype.list
    let failing = true
    const spy = vi.spyOn(ApiClient.prototype, 'list').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/claims') && failing) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    await openClaims(await session('monsoon', '17:05'), '?lang=en&screen=claims', 'error')
    expect(text('app-error')).toContain('Error code: internal_error')
    failing = false
    fireEvent.click(screen.getByTestId('app-error-retry'))
    await waitFor(() => expect(screen.getByTestId('screen-claims').getAttribute('data-state')).toBe('ready'))
    expect(spy.mock.calls.filter(([path]) => String(path).endsWith('/claims'))).toHaveLength(2)
  })

  it('keeps the list under the offline banner', async () => {
    await openClaims(await session('monsoon', '17:05'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-claims').getAttribute('data-state')).toBe('offline'))
    expect(text('app-offline-banner')).toMatch(/^Offline\. Showing data from/)
    expect(text('claim-card-CL-000142')).toContain('₹1,380')
  })
})

describe('Claims with a question about a payout (AC-22)', () => {
  it('gains a DISPUTE card for the case, above the claim, and the claim still reads ₹1,380', async () => {
    const kit = await session('monsoon', '17:12')
    await openClaims(kit)
    expect(screen.queryByTestId('claim-card-C-2291')).toBeNull()
    await act(async () => void (await kit.api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')))
    const card = await screen.findByTestId('claim-card-C-2291')
    expect(card.textContent).toContain('Question about a payout')
    expect(card.textContent).toContain('About claim CL-000142')
    expect(card.textContent).toContain('Question open')
    expect(card.textContent).toContain('₹1,380')
    expect(card.textContent).toContain('Question open · case C-2291. You will hear back within 24 hours.')
    expect(card.getAttribute('data-status')).toBe('DISPUTE_OPEN')
    const ids = within(screen.getByTestId('claims-list')).getAllByRole('listitem').map((item) => item.getAttribute('data-testid'))
    expect(ids).toEqual(['claim-card-C-2291', 'claim-card-CL-000142'])
    expect(text('claim-card-CL-000142')).toContain('₹1,380')
    expect(within(card).getByRole('link').getAttribute('href')).toMatch(/screen=claim&claim=CL-000142$/)
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('open_latest')
  })

  it('shows a closed question with the amount unchanged', async () => {
    stubClaims([disputeClosed(), claim()])
    await openClaims(await session('monsoon', '17:12'))
    const card = screen.getByTestId('claim-card-C-2291')
    expect(card.textContent).toContain('Question closed. Amount unchanged.')
    expect(card.textContent).toContain('Our team checked it. The amount paid stays ₹1,380.')
    expect(card.getAttribute('data-status')).toBe('DISPUTE_CLOSED')
  })
})

describe('Claims for a hospital-cash claim', () => {
  it('says "Waiting for your slip" with no amount, and "With a claims officer" with the clock once sent', async () => {
    stubClaims([personalWaitingForSlip()])
    await openClaims(await session('illness', '11:20'))
    const waiting = screen.getByTestId('claim-card-CL-000001')
    expect(waiting.textContent).toContain('Hospital cash')
    expect(waiting.textContent).toContain('Waiting for your slip')
    expect(waiting.textContent).not.toContain('₹')
    expect(waiting.getAttribute('data-status')).toBe('WAITING_FOR_SLIP')
  })

  it('shows a referred claim as with a claims officer and promises the clock of the rules', async () => {
    stubClaims([personalReferred()])
    await openClaims(await session('illness_mismatch', '11:20'))
    const card = screen.getByTestId('claim-card-CL-000001')
    expect(card.textContent).toContain('With a claims officer')
    expect(card.textContent).toContain('Next: a person decides. You will hear back within 24 hours.')
    expect(card.textContent).not.toContain('₹')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('open_latest')
  })
})

describe('Claims while the data loads', () => {
  it('draws skeletons and marks the screen busy', async () => {
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=claims', kit.backend)
    const root = screen.getByTestId('screen-claims')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    expect(within(root).getByTestId('app-skeleton')).toBeTruthy()
    await waitFor(() => expect(root.getAttribute('data-state')).not.toBe('loading'))
  })
})

describe('the open dispute fixture', () => {
  it('names the claim it is about, not its own id', () => {
    expect(disputeOpen().claim_id).toBeNull()
    expect(disputeOpen().disputed_claim_id).toBe('CL-000142')
  })
})

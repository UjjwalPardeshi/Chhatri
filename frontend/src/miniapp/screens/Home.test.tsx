/** S1 Home (fs-04 section 8): am I covered, what is happening, what next (AC-07, AC-08, AC-09, AC-38, AC-41). */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

async function openHome(merchant: string, at: string | null, search = '?lang=en') {
  const kit = testApi()
  backend = kit.backend
  if (at !== null) await kit.api.seek(at)
  const view = renderStandalone(`/merchant/${merchant}/app${search}`, kit.backend)
  await waitFor(() => expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('ready'))
  return { ...view, backend: kit.backend }
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''

describe('Home while the check-in waits for the slip (n3_slip_precheck)', () => {
  it('offers "Send the slip photo" from the open check-in, and opens the slip sheet', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n3_slip_precheck')
    const kit = testApi()
    backend = kit.backend
    await kit.api.load('illness')
    await kit.api.seek('11:30')
    renderStandalone('/merchant/S-0142/app?lang=en', kit.backend)
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('send_slip'))
    expect(text('app-nba-action')).toBe('Send the slip photo')
  })
})

describe('Home on a paid day (AC-07)', () => {
  it('says the cover sentence, the latest claim and why next', async () => {
    await openHome('S-0142', '17:05')
    expect(text('home-greeting')).toBe('Hello, Anil ji')
    expect(text('home-cover-status')).toBe('Your cover is active. Premium is paid through 22 August.')
    expect(text('home-prepaid-through')).toBe('22 August')
    expect(text('home-annual-used')).toBe('Used in the last 365 days: ₹1,380 of ₹30,000')
    expect(text('home-expected-day')).toContain('₹4,380')
    const claim = screen.getByTestId('home-latest-claim')
    expect(claim.textContent).toContain('₹1,380')
    expect(claim.textContent).toContain('Paid')
    expect(claim.textContent).toContain('Rain and lost sales')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_why')
    expect(screen.queryByTestId('home-open-buy')).toBeNull()
  })

  it('links the claim to its detail and the shortcut to the coverage screen', async () => {
    await openHome('S-0142', '17:05')
    const link = within(screen.getByTestId('home-latest-claim')).getByRole('link')
    expect(link.getAttribute('href')).toMatch(/\?lang=en&screen=claim&claim=CL-\d{6}$/)
    fireEvent.click(screen.getByTestId('home-open-coverage'))
    await screen.findByTestId('screen-coverage')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=coverage')
  })

  it('offers Ask Chhatri only while n2_ask_chhatri is on (copy deck home.btn.ask)', async () => {
    const off = await openHome('S-0142', '17:05')
    expect(screen.queryByTestId('home-open-ask')).toBeNull()
    off.unmount()
    backend.dispose()
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n2_ask_chhatri')
    await openHome('S-0142', '17:05')
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_why'))
    const ask = screen.getByTestId('home-open-ask')
    expect(ask.textContent).toBe('Ask Chhatri')
    expect(ask.getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=ask')
  })

  it('says Ask Chhatri once: when it is the next step, the bar carries it and the shortcut row is left out', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n2_ask_chhatri')
    await openHome('S-0142', '10:00')
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('ask'))
    expect(screen.queryByTestId('home-open-ask')).toBeNull()
    expect(text('app-nba-action')).toBe('Ask Chhatri')
    expect(screen.getAllByText('Ask Chhatri')).toHaveLength(1)
    expect(screen.getByTestId('home-open-coverage')).toBeTruthy()
  })

  it('shows the per-day price and the zone, and the loan instalment the merchant already has', async () => {
    await openHome('S-0142', '17:05')
    const card = screen.getByTestId('home-cover-card')
    expect(card.textContent).toContain('Premium a day')
    expect(card.textContent).toContain('₹18.62')
    expect(card.textContent).toContain('Parel')
    expect(card.textContent).toContain('Loan instalment a day')
    expect(card.textContent).toContain('₹600')
  })

  it('speaks Hindi by default for Anil, and labels the status in Hindi', async () => {
    await openHome('S-0142', '17:05', '')
    expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('hi')
    expect(text('home-greeting')).toBe('नमस्ते, अनिल जी')
    expect(text('home-cover-status')).toBe('आपका कवर चालू है। प्रीमियम 22 अगस्त तक जमा है।')
    expect(text('home-prepaid-through')).toBe('22 अगस्त')
    expect(screen.getByTestId('home-latest-claim').textContent).toContain('भुगतान हुआ')
  })

  it('names the brand in the app bar, so the heading of the cover card under it is not said twice', async () => {
    await openHome('S-0142', '17:05')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Chhatri')
    expect(within(screen.getByTestId('home-cover-card')).getByRole('heading').textContent).toBe('Your cover')
    expect(screen.getAllByText('Your cover')).toHaveLength(1)
  })
})

describe('Home with no cover (AC-08)', () => {
  it('reads "No cover yet", offers Get cover and says get_cover next', async () => {
    await openHome('S-0907', null)
    expect(text('home-cover-status')).toBe('No cover yet')
    expect(screen.getByTestId('home-open-buy').textContent).toBe('Get cover')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('get_cover')
    expect(screen.queryByTestId('home-latest-claim')).toBeNull()
    expect(screen.queryByTestId('home-prepaid-through')).toBeNull()
    expect(screen.queryByTestId('home-annual-used')).toBeNull()
  })

  it('opens the buy screen from Get cover, and never asks for a quote by viewing', async () => {
    const post = vi.spyOn(ApiClient.prototype, 'post')
    await openHome('S-0907', null)
    expect(post).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('home-open-buy'))
    await screen.findByTestId('screen-buy')
    expect(post).not.toHaveBeenCalled()
  })
})

describe('Home during an alert (AC-09)', () => {
  it('names the alert, carries a SIMULATED badge and shows no offer of any kind', async () => {
    await openHome('S-0142', '15:00')
    const banner = screen.getByTestId('home-alert-banner')
    expect(banner.textContent).toContain('A-20250818-01')
    expect(banner.textContent).toContain('14:00')
    expect(banner.textContent).toContain('A weather alert is on for your area. Chhatri is watching')
    expect(within(banner).getByTestId('home-alert-mode').getAttribute('data-mode')).toBe('SIMULATED')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('alert_notice')
    expect(screen.getByTestId('screen-home').textContent).not.toMatch(/loan offer|top-up|top up|offer|cross-sell/i)
  })

  it('has no banner when no alert is in force', async () => {
    await openHome('S-0142', '17:05')
    expect(screen.getByTestId('home-alert-banner')).toBeTruthy()
    backend.dispose()
    const kit = testApi()
    backend = kit.backend
    await kit.api.seek('10:00')
    renderStandalone('/merchant/S-0142/app?lang=en', kit.backend)
    await waitFor(() => expect(screen.getAllByTestId('screen-home').at(-1)?.getAttribute('data-state')).toBe('ready'))
    expect(screen.getAllByTestId('home-alert-banner').length).toBeLessThanOrEqual(1)
  })
})

describe('Home when something fails (AC-38)', () => {
  it('shows the error state with the code, and Retry fetches the cover again', async () => {
    const real = ApiClient.prototype.get
    let failing = true
    const calls: string[] = []
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/cover')) {
        calls.push(path)
        if (failing) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      }
      return real.call(this, path, signal)
    })
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en', kit.backend)
    await waitFor(() => expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('Something went wrong. Try again.')
    expect(text('app-error')).toContain('Error code: internal_error')
    expect(screen.queryByTestId('app-nba')).toBeNull()
    failing = false
    fireEvent.click(screen.getByTestId('app-error-retry'))
    await waitFor(() => expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('ready'))
    expect(calls.length).toBe(2)
  })

  it('keeps the cover card when only the claims fail, and puts the error and Retry in the claim slot', async () => {
    const real = ApiClient.prototype.list
    vi.spyOn(ApiClient.prototype, 'list').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/claims')) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    const kit = testApi()
    backend = kit.backend
    await kit.api.seek('17:05')
    renderStandalone('/merchant/S-0142/app?lang=en', kit.backend)
    await waitFor(() => expect(screen.getByTestId('home-cover-status')).toBeTruthy())
    expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('ready')
    const slot = await screen.findByTestId('home-claim-error')
    expect(within(slot).getByTestId('app-error-retry')).toBeTruthy()
    expect(screen.queryByTestId('home-latest-claim')).toBeNull()
  })

  it('shows the offline banner with the data still on screen, and the next action disabled with a reason (AC-39)', async () => {
    await openHome('S-0142', '17:05')
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('offline'))
    expect(text('app-offline-banner')).toMatch(/^Offline\. Showing data from/)
    expect(text('home-cover-status')).toContain('Your cover is active')
    expect((screen.getByTestId('app-nba-action') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('Home follows the replay clock (AC-41)', () => {
  it('loses the paid claim, and the why next action, when the replay is moved back', async () => {
    const view = await openHome('S-0142', '17:05')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_why')
    await waitFor(() => expect(screen.getByTestId('probe-location').getAttribute('data-stream')).toBe('open'))
    await act(async () => void (await view.api.seek('16:00')))
    await waitFor(() => expect(screen.queryByTestId('home-latest-claim')).toBeNull())
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).not.toBe('see_why'))
    expect(text('app-clock')).toContain('16:00')
  })
})

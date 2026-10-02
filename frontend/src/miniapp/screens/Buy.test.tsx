/** S3 Buy (fs-04 section 8): a quote for the waiting period, an honest BLOCKED, a simulated link, a payment that refetches Home (AC-13 to AC-17). */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { PremiumLinkResult } from '../../api/types'
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
})

type Options = { merchant?: string; search?: string; scenario?: 'buy_cover'; prepare?: (kit: ReturnType<typeof testApi>) => void }

async function openBuy({ merchant = 'S-0907', search = '?lang=en&screen=buy', scenario = 'buy_cover', prepare }: Options = {}) {
  const kit = testApi()
  backend = kit.backend
  await kit.api.load(scenario)
  prepare?.(kit)
  renderStandalone(`/merchant/${merchant}/app${search}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId('screen-buy').getAttribute('data-state')).toBe('ready'))
  return kit
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const check = async () => {
  fireEvent.click(await screen.findByTestId('buy-check'))
  return screen.findByTestId('buy-result')
}

describe('a merchant with no cover, asking while an alert is on', () => {
  it('tells the truth: blocked, starts 25 August, with the price and the first payment, never "Approved"', async () => {
    await openBuy()
    expect(text('screen-buy')).toContain('New cover always starts 7 days after you ask.')
    const result = await check()
    expect(result.getAttribute('data-outcome')).toBe('BLOCKED')
    expect(result.textContent).toContain('Blocked for now. Cover starts on 25 August.')
    expect(text('buy-starts-on')).toBe('25 August')
    expect(text('buy-price-per-day')).toBe('₹14.16')
    expect(text('buy-first-payment')).toBe('₹424.80')
    expect(text('screen-buy')).toContain('does not pay for that alert')
    expect(text('screen-buy')).not.toMatch(/approved/i)
  })

  it('labels the link SIMULATED, opens nothing, and a tap on simulate shows the new start date and refetches Home', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    await openBuy()
    await check()
    expect(text('buy-link-mode')).toContain('SIMULATED')
    expect(screen.getByTestId('buy-link-mode').getAttribute('data-mode')).toBe('SIMULATED')
    expect(screen.queryByTestId('buy-pay-live')).toBeNull()
    fireEvent.click(screen.getByTestId('buy-simulate-pay'))
    await screen.findByTestId('buy-paid')
    expect(text('buy-paid')).toContain('Payment received.')
    expect(text('buy-paid')).toContain('25 August')
    expect(open).not.toHaveBeenCalled()
  })

  it('shows the next step after the check and after the payment', async () => {
    await openBuy()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('check_price'))
    await check()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('pay'))
    fireEvent.click(screen.getByTestId('buy-simulate-pay'))
    await screen.findByTestId('buy-paid')
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('home_after_paid'))
  })
})

describe('an OK quote', () => {
  it('says cover starts on the date the quote gives and carries no blocked note', async () => {
    await openBuy({
      prepare: ({ api }) => {
        const real = api.premiumLink.bind(api)
        vi.spyOn(api, 'premiumLink').mockImplementation(async (id: string): Promise<PremiumLinkResult> => {
          const result = await real(id)
          return { ...result, quote: { ...result.quote, outcome: 'OK' } }
        })
      },
    })
    const result = await check()
    expect(result.getAttribute('data-outcome')).toBe('OK')
    expect(result.textContent).toContain('Cover starts on 25 August')
    expect(text('screen-buy')).not.toContain('does not pay for that alert')
  })
})

describe('Hindi', () => {
  it('words the screen in Hindi with the same numbers', async () => {
    await openBuy({ search: '?lang=hi&screen=buy' })
    const result = await check()
    expect(result.textContent).toContain('25 अगस्त')
    expect(text('buy-first-payment')).toBe('₹424.80')
  })
})

describe('errors and states', () => {
  it('says the demo needs the presenter when the session is refused', async () => {
    await openBuy({ prepare: ({ api }) => void vi.spyOn(api, 'premiumLink').mockRejectedValue(new ApiError('unauthorized', 'no', 401)) })
    fireEvent.click(await screen.findByTestId('buy-check'))
    expect((await screen.findByTestId('buy-error')).textContent).toContain("presenter's session")
  })

  it('says the link could not be made when the quote has none', async () => {
    await openBuy({
      prepare: ({ api }) => {
        const real = api.premiumLink.bind(api)
        vi.spyOn(api, 'premiumLink').mockImplementation(async (id: string) => ({ ...(await real(id)), premium: null }))
      },
    })
    fireEvent.click(await screen.findByTestId('buy-check'))
    expect((await screen.findByTestId('buy-error')).textContent).toContain("payment link couldn't be created")
  })

  it('says the payment did not go through, and lets the merchant try again', async () => {
    const kit = await openBuy()
    await check()
    vi.spyOn(kit.api, 'paytmWebhook').mockRejectedValueOnce(new ApiError('internal_error', 'x', 500))
    fireEvent.click(screen.getByTestId('buy-simulate-pay'))
    expect((await screen.findByTestId('buy-error')).textContent).toContain('No money was taken')
    fireEvent.click(screen.getByTestId('buy-simulate-pay'))
    await screen.findByTestId('buy-paid')
  })

  it('shows a status card and no buy button to a merchant who already has cover', async () => {
    await openBuy({ merchant: 'S-0142', scenario: 'buy_cover' })
    expect(screen.queryByTestId('buy-check')).toBeNull()
    expect(screen.getByTestId('buy-cover-card')).toBeTruthy()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('home_when_covered'))
  })

  it('disables the check offline and says why', async () => {
    await openBuy()
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    fireEvent(window, new Event('offline'))
    await waitFor(() => expect((screen.getByTestId('buy-check') as HTMLButtonElement).disabled).toBe(true))
    expect(document.body.textContent).toContain('This needs the internet')
  })
})

const box = (purpose: string) => screen.getByTestId(`buy-consent-${purpose}`) as HTMLInputElement

describe('the consent block (n6_consents, fs-07 9.5, AC-N6-08)', () => {
  beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n6_consents'))
  afterEach(() => vi.unstubAllEnvs())

  it('shows the notice and three unticked boxes, and keeps the check disabled until both required boxes are ticked', async () => {
    await openBuy()
    expect(await screen.findByTestId('buy-consent-notice')).toBeTruthy()
    expect(text('buy-consent-notice')).toContain('Before you pay')
    expect(text('buy-consent-version')).toBe('Notice version notice-1')
    expect([box('SALES_DATA_FOR_CLAIM'), box('SLIP_DATA_FOR_HOSPITAL_CLAIM'), box('SETTLEMENT_DEDUCTION')].map((b) => b.checked)).toEqual([false, false, false])
    expect(text('screen-buy')).toContain('Needed for cover')
    expect(text('screen-buy')).toContain('Optional')
    expect((screen.getByTestId('buy-check') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByTestId('buy-consent-hint')).toBeTruthy()
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('tick_consent')
    fireEvent.click(box('SALES_DATA_FOR_CLAIM'))
    expect((screen.getByTestId('buy-check') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(box('SETTLEMENT_DEDUCTION'))
    await waitFor(() => expect((screen.getByTestId('buy-check') as HTMLButtonElement).disabled).toBe(false))
    expect(screen.queryByTestId('buy-consent-hint')).toBeNull()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('check_price'))
  })

  it('sends the ticks with the quote; after payment sales and settlement are ACTIVE from the app, the slip not given', async () => {
    const kit = await openBuy()
    fireEvent.click(await screen.findByTestId('buy-consent-SALES_DATA_FOR_CLAIM'))
    fireEvent.click(box('SETTLEMENT_DEDUCTION'))
    await check()
    fireEvent.click(screen.getByTestId('buy-simulate-pay'))
    await screen.findByTestId('buy-paid')
    const [sales, slip, settlement] = await kit.api.consents('S-0907')
    expect([sales.status, slip.status, settlement.status]).toEqual(['ACTIVE', 'NOT_GIVEN', 'ACTIVE'])
    expect(sales.source).toBe('PAYMENT_APP')
  })

  it('says the notice changed on a 422, clears the ticks and reads the consents again', async () => {
    const kit = await openBuy({ prepare: (k) => vi.spyOn(k.api, 'premiumLink').mockRejectedValue(new ApiError('validation_error', 'consent is incomplete', 422, { notice_version: 'out of date' })) })
    const reads = vi.spyOn(kit.api, 'consents')
    fireEvent.click(await screen.findByTestId('buy-consent-SALES_DATA_FOR_CLAIM'))
    fireEvent.click(box('SETTLEMENT_DEDUCTION'))
    fireEvent.click(screen.getByTestId('buy-check'))
    expect((await screen.findByTestId('buy-consent-error')).textContent).toBe('The notice changed. Please read it again.')
    await waitFor(() => expect(reads).toHaveBeenCalled())
    await waitFor(() => expect(box('SALES_DATA_FOR_CLAIM').checked).toBe(false))
  })

  it('asks nothing of a merchant who already has cover', async () => {
    await openBuy({ merchant: 'S-0142' })
    expect(screen.queryByTestId('buy-consent-notice')).toBeNull()
  })
})

describe('the consent block with n6_consents off', () => {
  it('is not shown, and the check is enabled at once', async () => {
    await openBuy()
    expect(screen.queryByTestId('buy-consent-notice')).toBeNull()
    expect((screen.getByTestId('buy-check') as HTMLButtonElement).disabled).toBe(false)
  })
})

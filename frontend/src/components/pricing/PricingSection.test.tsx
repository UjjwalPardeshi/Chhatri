/** "Price the cover" on the Backtest page (H24 pricing simulator): the flag, a priced answer, debounced levers and abort, the marks and Reset, the zone picker, the unavailable and error states, and the deep link. */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { Api } from '../../api/endpoints'
import { parsePricing, type Pricing, type PricingLevers } from '../../api/pricing'
import { AppRoutes } from '../../App'
import type { MockBackend } from '../../mock/backend'
import { PRICING_ONLY_ON_BACKEND } from '../../mock/endpoints/pricing'
import { testApi, testBackend } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { PRICING_DATA } from '../../test/pricingFixture'
import { renderApp } from '../../test/renderApp'
import { AppShell } from '../layout/AppShell'
import { PRICING_CAPTION } from './pricingModel'

const ANSWER: Pricing = parsePricing(PRICING_DATA)
const PUBLISHED: PricingLevers = { floor_pct: 50, share_pct: 50, cap_rupees: 2500, loading_pct: 35 }

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  vi.stubEnv('VITE_FEATURES', 'h24_whatif')
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

/** The fixture's figures with the levers the request asked for (null: the published rules). */
const echo = (levers: PricingLevers | null): Pricing => ({ ...ANSWER, levers: levers ?? ANSWER.levers })
const fakePricing = () => vi.fn<Api['pricing']>((levers) => Promise.resolve(echo(levers)))

/** The console against the mock backend, with the pricing call replaced. */
function renderWith(pricing: Api['pricing'], path = '/backtest') {
  const kit = testApi(backend)
  render(
    <MemoryRouter initialEntries={[path]}>
      <LiveProvider api={{ ...kit.api, pricing }} mock>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LiveProvider>
    </MemoryRouter>,
  )
}

const section = () => screen.getByRole('region', { name: 'Price the cover' })
const slider = (name: string) => within(section()).getByRole('slider', { name }) as HTMLInputElement
const leverValue = (name: string) => slider(name).closest('.pricing-lever')?.querySelector('.pricing-lever__value')?.textContent
const floorButton = (name: string) => within(screen.getByRole('group', { name: 'Index floor' })).getByRole('button', { name })
const zonePicker = () => within(section()).getByRole('combobox', { name: 'Zone' }) as HTMLSelectElement
const resetButton = () => within(section()).getByRole('button', { name: 'Reset to the published rules' }) as HTMLButtonElement
const marks = () => within(section()).queryAllByText(/^published /).map((node) => node.textContent)
const lastLevers = (pricing: ReturnType<typeof fakePricing>) => pricing.mock.calls.at(-1)?.[0]

/** The value of one of the chosen zone's figures, by its label. */
function figure(label: string): string | null | undefined {
  return within(screen.getByTestId('pricing-zone')).getByText(label).parentElement?.querySelector('dd')?.textContent
}

describe('the pricing section', () => {
  it('is not on the Backtest page while h24_whatif is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    renderApp('/backtest', backend)
    expect((await screen.findAllByText(/simulated sales · real Open-Meteo rainfall/)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('heading', { name: 'Price the cover' })).toBeNull()
    expect(document.getElementById('pricing')).toBeNull()
  })

  it("is there with the flag, and against the mock says it needs the backend's pricing table, with no price", async () => {
    renderApp('/backtest', backend)
    const box = await screen.findByTestId('pricing-unavailable')
    expect(box.textContent).toContain("The pricing simulator needs the backend's pricing table.")
    expect(box.textContent).toContain(PRICING_ONLY_ON_BACKEND)
    expect(section().id).toBe('pricing')
    expect(within(section()).queryByRole('slider')).toBeNull()
    expect(within(section()).queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(section().textContent).not.toContain('₹')
    expect(section().textContent).toContain(PRICING_CAPTION)
  })

  it("shows the priced answer: Anil's Z7 first, its eight figures, the city line, the published levers and the caption", async () => {
    const pricing = fakePricing()
    renderWith(pricing)
    await screen.findByTestId('pricing-zone')
    expect(pricing).toHaveBeenCalledWith(null, expect.any(AbortSignal))
    expect(zonePicker().value).toBe('Z7')
    expect([...zonePicker().options].map((o) => o.textContent)).toEqual(['Z7 · Parel · Lalbaug', 'Z8 · Dadar · Mahim', 'Z21 · Borivali'])
    expect(figure('Premium per day')).toBe('₹18.62')
    expect(figure('Premium per month')).toBe('₹558.60')
    expect(figure('Premium per year')).toBe('₹6,796.30')
    expect(figure('Expected payout per shop')).toBe('₹4,417.91 a year')
    expect(figure('Payout days')).toBe('3 a year')
    expect(figure('Covered shops')).toBe('46')
    expect(figure("Today's premium")).toBe('₹18.62 a day')
    expect(figure("Loss ratio at today's price")).toBe('65%')
    const city = screen.getByTestId('pricing-city')
    expect(within(city).getByText('Premium per day ₹6.93 lowest · ₹16.43 median · ₹38.82 highest')).toBeTruthy()
    expect(within(city).getByText('At a 50% floor')).toBeTruthy()
    expect(within(city).getByText('89 of 148 real drops paid (60%) · 36 of 125 payouts on a day with no real drop (29%)')).toBeTruthy()
    expect(['40%', '45%', '50%', '55%', '60%'].map((name) => floorButton(name).getAttribute('aria-pressed'))).toEqual(['false', 'false', 'true', 'false', 'false'])
    expect([leverValue('Payout share'), leverValue('Area daily cap'), leverValue('Loading')]).toEqual(['50%', '₹2,500', '35%'])
    expect(marks()).toEqual([])
    expect(resetButton().disabled).toBe(true)
    expect(within(section()).getByText('Read-only: nothing is saved.')).toBeTruthy()
    expect(within(section()).getByText(PRICING_CAPTION)).toBeTruthy()
  })

  it('waits 250 ms, sends one request for a burst of changes, and aborts the one in flight', async () => {
    const pricing = vi.fn<Api['pricing']>((levers) => (levers?.share_pct === 55 ? new Promise<Pricing>(() => undefined) : Promise.resolve(echo(levers))))
    renderWith(pricing)
    await screen.findByTestId('pricing-zone')
    fireEvent.change(slider('Payout share'), { target: { value: '45' } })
    fireEvent.change(slider('Payout share'), { target: { value: '55' } })
    await act(() => new Promise((resolve) => setTimeout(resolve, 150)))
    expect(pricing).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(pricing).toHaveBeenCalledTimes(2))
    expect(pricing.mock.calls[1][0]).toEqual({ ...PUBLISHED, share_pct: 55 })
    expect(within(section()).getByText('Recomputing…')).toBeTruthy()
    const inFlight = pricing.mock.calls[1][1]
    fireEvent.change(slider('Payout share'), { target: { value: '60' } })
    expect(inFlight?.aborted).toBe(true)
    await waitFor(() => expect(pricing).toHaveBeenCalledTimes(3))
    expect(pricing.mock.calls[2][0]).toEqual({ ...PUBLISHED, share_pct: 60 })
    await waitFor(() => expect(within(section()).queryByText('Recomputing…')).toBeNull())
    expect(leverValue('Payout share')).toBe('60%')
  })

  it('marks every lever that differs from the published rules, and Reset sends the published levers', async () => {
    const pricing = fakePricing()
    renderWith(pricing)
    await screen.findByTestId('pricing-zone')
    fireEvent.click(floorButton('55%'))
    fireEvent.change(slider('Area daily cap'), { target: { value: '3000' } })
    fireEvent.change(slider('Loading'), { target: { value: '30' } })
    await waitFor(() => expect(lastLevers(pricing)).toEqual({ floor_pct: 55, share_pct: 50, cap_rupees: 3000, loading_pct: 30 }))
    expect(pricing).toHaveBeenCalledTimes(2)
    expect(floorButton('55%').getAttribute('aria-pressed')).toBe('true')
    expect([leverValue('Area daily cap'), leverValue('Loading')]).toEqual(['₹3,000', '30%'])
    expect(marks()).toEqual(['published 50%', 'published ₹2,500', 'published 35%'])
    expect(slider('Payout share').closest('.pricing-lever')?.getAttribute('data-changed')).toBe('false')
    expect(await within(screen.getByTestId('pricing-city')).findByText('At a 55% floor')).toBeTruthy()
    expect(resetButton().disabled).toBe(false)
    fireEvent.click(resetButton())
    await waitFor(() => expect(pricing).toHaveBeenCalledTimes(3))
    expect(lastLevers(pricing)).toEqual(PUBLISHED)
    expect(marks()).toEqual([])
    expect(resetButton().disabled).toBe(true)
    expect(floorButton('50%').getAttribute('aria-pressed')).toBe('true')
    expect(slider('Area daily cap').value).toBe('2500')
  })

  it('keeps every change made in one go: a second lever never undoes the first', async () => {
    const pricing = fakePricing()
    renderWith(pricing)
    await screen.findByTestId('pricing-zone')
    act(() => {
      floorButton('55%').click()
      fireEvent.change(slider('Payout share'), { target: { value: '100' } })
    })
    await waitFor(() => expect(pricing).toHaveBeenCalledTimes(2))
    expect(lastLevers(pricing)).toEqual({ ...PUBLISHED, floor_pct: 55, share_pct: 100 })
  })

  it('switches the figures with the zone picker, without a request', async () => {
    const pricing = fakePricing()
    renderWith(pricing)
    await screen.findByTestId('pricing-zone')
    fireEvent.change(zonePicker(), { target: { value: 'Z8' } })
    expect(figure('Premium per day')).toBe('₹38.82')
    expect(figure('Premium per year')).toBe('₹14,169.30')
    expect(figure('Payout days')).toBe('6 a year')
    expect(figure('Covered shops')).toBe('99')
    await act(() => new Promise((resolve) => setTimeout(resolve, 300)))
    expect(pricing).toHaveBeenCalledTimes(1)
  })

  it("says not priced today for a zone with no premium today, and when today's price would pay out more than it collects", async () => {
    // Z7 as the real route prices it at floor 40%, share 100%, cap ₹10,000, loading 0%.
    const z7 = { ...ANSWER.zones[0], triggers: 5, expected_payout_per_year_paise: 794_247, premium_per_day_paise: 2176, premium_per_month_paise: 65_280, premium_per_year_paise: 794_240, payout_days_per_year: 2.5, loss_ratio_at_current_price: 1.1686 }
    const z21 = { ...ANSWER.zones[2], current_premium_per_day_paise: null, loss_ratio_at_current_price: null }
    renderWith(() => Promise.resolve({ ...ANSWER, zones: [z7, ANSWER.zones[1], z21] }))
    await screen.findByTestId('pricing-zone')
    expect(figure("Loss ratio at today's price")).toBe('117%')
    expect(figure('Payout days')).toBe('2.5 a year')
    expect(within(screen.getByTestId('pricing-zone')).getByText('pays out more than it collects')).toBeTruthy()
    fireEvent.change(zonePicker(), { target: { value: 'Z21' } })
    expect(figure("Today's premium")).toBe('not priced today')
    expect(figure("Loss ratio at today's price")).toBe('not priced today')
    expect(within(screen.getByTestId('pricing-zone')).queryByText('pays out more than it collects')).toBeNull()
  })

  it('says it needs the pricing table when the backend has none, with its message', async () => {
    renderWith(() => Promise.reject(new ApiError('not_found', 'the pricing table is not built yet (python -m chhatri.backtest.pricing)', 404)))
    const box = await screen.findByTestId('pricing-unavailable')
    expect(box.textContent).toContain("The pricing simulator needs the backend's pricing table.")
    expect(box.textContent).toContain('python -m chhatri.backtest.pricing')
  })

  it('shows any other error with a retry, and prices once the retry works', async () => {
    const pricing = vi.fn<Api['pricing']>((levers) => Promise.resolve(echo(levers))).mockRejectedValueOnce(new ApiError('internal', 'internal error', 500))
    renderWith(pricing)
    expect(await within(section()).findByText('Could not load this')).toBeTruthy()
    expect(screen.queryByTestId('pricing-unavailable')).toBeNull()
    fireEvent.click(within(section()).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByTestId('pricing-zone')).toBeTruthy()
    expect(pricing).toHaveBeenCalledTimes(2)
  })
})

describe('the deep link /backtest#pricing', () => {
  it('scrolls the section into view once the page above has rendered, and only once', async () => {
    const scrolled: { id: string; heroShown: boolean }[] = []
    vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(function record(this: Element) {
      scrolled.push({ id: this.id, heroShown: document.querySelector('.backtest-hero') !== null })
    })
    const pricing = fakePricing()
    renderWith(pricing, '/backtest#pricing')
    await screen.findByTestId('pricing-zone')
    await waitFor(() => expect(scrolled).toEqual([{ id: 'pricing', heroShown: true }]))
    fireEvent.change(slider('Payout share'), { target: { value: '60' } })
    await waitFor(() => expect(pricing).toHaveBeenCalledTimes(2))
    expect(scrolled).toHaveLength(1)
  })

  it('does not scroll without the hash', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(() => undefined)
    renderWith(fakePricing())
    await screen.findByTestId('pricing-zone')
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)))
    expect(scroll).not.toHaveBeenCalled()
  })
})
